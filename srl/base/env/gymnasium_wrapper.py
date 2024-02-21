import logging
import os
import pickle
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union, cast

import gymnasium
import numpy as np
from gymnasium import spaces as gym_spaces
from gymnasium.spaces import flatten, flatten_space
from srl.base import spaces as srl_spaces
from srl.base.define import (
    DoneTypes,
    EnvActionType,
    EnvObservationTypes,
    InfoType,
    KeyBindType,
    RenderModes,
    RLInvalidActionType,
    RLTypes,
)
from srl.base.env.base import EnvBase, SpaceBase
from srl.base.env.config import EnvConfig

if TYPE_CHECKING:
    from srl.base.rl.base import RLWorker


logger = logging.getLogger(__name__)


"""
・gym_spaceを1次元にして管理する
・decodeもあるので順序を保持する
・変換できないものはエラーログを出力して無視する
"""


def _space_change_from_gym_to_srl_sub(gym_space: gym_spaces.Space) -> Optional[Union[SpaceBase, List[SpaceBase]]]:
    if isinstance(gym_space, gym_spaces.Discrete):
        if hasattr(gym_space, "start"):
            return srl_spaces.DiscreteSpace(int(gym_space.n), start=int(gym_space.start))
        else:
            return srl_spaces.DiscreteSpace(int(gym_space.n))

    if isinstance(gym_space, gym_spaces.MultiDiscrete):
        return srl_spaces.BoxSpace(gym_space.shape, 0, gym_space.nvec, dtype=np.int64)

    if isinstance(gym_space, gym_spaces.MultiBinary):
        return srl_spaces.BoxSpace(gym_space.shape, 0, 1, dtype=np.int8)

    if isinstance(gym_space, gym_spaces.Box):
        return srl_spaces.BoxSpace(gym_space.shape, gym_space.low, gym_space.high, gym_space.dtype)

    if isinstance(gym_space, gym_spaces.Tuple):
        sub_spaces = []
        for c in gym_space.spaces:
            sub_space = _space_change_from_gym_to_srl_sub(c)
            if sub_space is None:
                continue
            if isinstance(sub_space, list):
                sub_spaces.extend(sub_space)
            else:
                sub_spaces.append(sub_space)
        return sub_spaces

    if isinstance(gym_space, gym_spaces.Dict):
        sub_spaces = []
        for k in sorted(gym_space.spaces.keys()):
            space = gym_space.spaces[k]
            sub_space = _space_change_from_gym_to_srl_sub(space)
            if sub_space is None:
                continue
            if isinstance(sub_space, list):
                sub_spaces.extend(sub_space)
            else:
                sub_spaces.append(sub_space)
        return sub_spaces

    if isinstance(gym_space, gym_spaces.Graph):
        pass  # not support

    if isinstance(gym_space, gym_spaces.Text):
        shape = (gym_space.max_length,)
        return srl_spaces.BoxSpace(shape, 0, len(gym_space.character_set), np.int64)

    if isinstance(gym_space, gym_spaces.Sequence):
        pass  # not support

    # ---- other space
    try:
        flat_space = flatten_space(gym_space)
        if isinstance(flat_space, gym_spaces.Box):
            return srl_spaces.BoxSpace(flat_space.shape, flat_space.low, flat_space.high, flat_space.dtype)
    except NotImplementedError as e:
        logger.warning(f"Ignored for unsupported space. type '{type(gym_space)}', err_msg '{e}'")

    return None


def space_change_from_gym_to_srl(gym_space: gym_spaces.Space) -> SpaceBase:
    # tupleかdictがあればarrayにして管理、そうじゃない場合はそのまま
    srl_space = _space_change_from_gym_to_srl_sub(gym_space)
    assert srl_space is not None
    if isinstance(srl_space, list):
        srl_space = srl_spaces.ArraySpace(srl_space)
    return srl_space


def _space_encode_from_gym_to_srl_sub(gym_space: gym_spaces.Space, x: Any):
    # xは生データの可能性もあるので、最低限gymが期待している型に変換
    if isinstance(gym_space, gym_spaces.Discrete):
        return int(x)
    if isinstance(gym_space, gym_spaces.MultiDiscrete):
        return np.asarray(x, dtype=gym_space.dtype)
    if isinstance(gym_space, gym_spaces.MultiBinary):
        return np.asarray(x, dtype=gym_space.dtype)
    if isinstance(gym_space, gym_spaces.Box):
        return np.asarray(x, dtype=gym_space.dtype)
    if isinstance(gym_space, gym_spaces.Tuple):
        s = cast(Any, gym_space.spaces)
        arr = []
        for space, x_part in zip(s, x):
            _x = _space_encode_from_gym_to_srl_sub(space, x_part)
            if _x is None:
                continue
            if isinstance(_x, list):
                arr.extend(_x)
            else:
                arr.append(_x)
        return arr
    if isinstance(gym_space, gym_spaces.Dict):
        arr = []
        for key in sorted(gym_space.spaces.keys()):
            _x = _space_encode_from_gym_to_srl_sub(gym_space.spaces[key], x[key])
            if _x is None:
                continue
            if isinstance(_x, list):
                arr.extend(_x)
            else:
                arr.append(_x)
        return arr

    if isinstance(gym_space, gym_spaces.Graph):
        pass  # not support

    if isinstance(gym_space, gym_spaces.Text):
        arr = [gym_space.character_index(v) for v in x]
        return arr

    if isinstance(gym_space, gym_spaces.Sequence):
        pass  # not support

    # ---- other space
    try:
        x = flatten(gym_space, x)
        if isinstance(x, np.ndarray):
            return x
    except NotImplementedError as e:
        logger.debug(f"Ignored for unsupported space. type '{type(gym_space)}', '{x}', err_msg '{e}'")

    return None


def space_encode_from_gym_to_srl(gym_space: gym_spaces.Space, val: Any):
    x = _space_encode_from_gym_to_srl_sub(gym_space, val)
    assert x is not None, "Space flatten encode failed."
    return x


def _space_decode_to_srl_from_gym_sub(gym_space: gym_spaces.Space, x: Any, idx=0):
    if isinstance(gym_space, gym_spaces.Discrete):
        return x[idx], idx + 1
    if isinstance(gym_space, gym_spaces.MultiDiscrete):
        return x[idx], idx + 1
    if isinstance(gym_space, gym_spaces.MultiBinary):
        return x[idx], idx + 1
    if isinstance(gym_space, gym_spaces.Box):
        return x[idx], idx + 1
    if isinstance(gym_space, gym_spaces.Tuple):
        arr = []
        for space in gym_space.spaces:
            y, idx = _space_decode_to_srl_from_gym_sub(space, x, idx)
            arr.append(y)
        return tuple(arr), idx

    if isinstance(gym_space, gym_spaces.Dict):
        keys = sorted(gym_space.spaces.keys())
        dic = {}
        for key in keys:
            y, idx = _space_decode_to_srl_from_gym_sub(gym_space.spaces[key], x, idx)
            dic[key] = y
        return dic, idx

    if isinstance(gym_space, gym_spaces.Graph):
        pass  # not support

    if isinstance(gym_space, gym_spaces.Text):
        pass  # TODO

    if isinstance(gym_space, gym_spaces.Sequence):
        pass  # not support

    # 不明なのはsampleがあればそれを適用、なければNone
    if hasattr(gym_space, "sample"):
        y = gym_space.sample()
    else:
        y = None
    return y, idx


def space_decode_to_srl_from_gym(gym_space: gym_spaces.Space, srl_space: SpaceBase, val: Any) -> Any:
    if not isinstance(srl_space, srl_spaces.ArraySpace):
        val = [val]
    val, _ = _space_decode_to_srl_from_gym_sub(gym_space, val)
    assert val is not None, "Space flatten decode failed."
    return val


class GymnasiumWrapper(EnvBase):
    def __init__(self, config: EnvConfig):
        self.config = config
        self.seed = None

        os.environ["SDL_VIDEODRIVER"] = "dummy"
        logger.info("set SDL_VIDEODRIVER='dummy'")

        self.env = self.make_gymnasium_env()
        logger.info(f"gym action_space: {self.env.action_space}")
        logger.info(f"gym obs_space   : {self.env.observation_space}")

        # metadata
        self.fps = 60
        self.render_mode = RenderModes.none
        self.render_modes = ["ansi", "human", "rgb_array"]
        if hasattr(self.env, "metadata"):
            logger.info(f"gym metadata    : {self.env.metadata}")
            self.fps = self.env.metadata.get("render_fps", 60)
            self.render_modes = self.env.metadata.get("render_modes", ["ansi", "human", "rgb_array"])

        _act_space = None
        _obs_type = EnvObservationTypes.UNKNOWN
        _obs_space = None

        # --- wrapper
        for wrapper in config.gym_wrappers:
            _act_space = wrapper.action_space(_act_space, self.env)
            _obs_type, _obs_space = wrapper.observation_space(_obs_type, _obs_space, self.env)

        # --- space img
        self.enable_flatten_observation = False
        if _obs_space is None:
            if config.gym_check_image:
                if isinstance(self.env.observation_space, gym_spaces.Box) and (
                    "uint" in str(self.env.observation_space.dtype)
                ):
                    if len(self.env.observation_space.shape) == 2:
                        _obs_type = EnvObservationTypes.GRAY_2ch
                    elif len(self.env.observation_space.shape) == 3:
                        # w,h,ch 想定
                        ch = self.env.observation_space.shape[-1]
                        if ch == 1:
                            _obs_type = EnvObservationTypes.GRAY_3ch
                        elif ch == 3:
                            _obs_type = EnvObservationTypes.COLOR
                        else:
                            _obs_type = EnvObservationTypes.IMAGE

                    if _obs_type != EnvObservationTypes.UNKNOWN:
                        # 画像はそのままのshape
                        self.enable_flatten_observation = False
                        _obs_space = srl_spaces.BoxSpace(
                            self.env.observation_space.shape,
                            self.env.observation_space.low,
                            self.env.observation_space.high,
                        )

            # --- space obs
            if _obs_type == EnvObservationTypes.UNKNOWN:
                self.enable_flatten_observation = True
                _obs_space = space_change_from_gym_to_srl(self.env.observation_space)
                if _obs_space.rl_type != RLTypes.DISCRETE:
                    if self.config.gym_prediction_by_simulation and self._pred_space_discrete():
                        _obs_type = EnvObservationTypes.DISCRETE
                    else:
                        _obs_type = EnvObservationTypes.CONTINUOUS
                else:
                    _obs_type = EnvObservationTypes.DISCRETE

        # --- space action
        if _act_space is None:
            self.enable_flatten_action = True
            _act_space = space_change_from_gym_to_srl(self.env.action_space)
        else:
            self.enable_flatten_action = False

        assert _obs_space is not None
        self._action_space: SpaceBase = _act_space
        self._observation_type = _obs_type
        self._observation_space: SpaceBase = _obs_space

        logger.info(f"obs_type   : {self._observation_type}")
        logger.info(f"observation: {self._observation_space}")
        logger.info(f"flatten_obs: {self.enable_flatten_observation}")
        logger.info(f"action     : {self._action_space}")
        logger.info(f"flatten_act: {self.enable_flatten_action}")

    def make_gymnasium_env(self, **kwargs) -> gymnasium.Env:
        if self.config.gymnasium_make_func is None:
            return gymnasium.make(self.config.name, **self.config.kwargs, **kwargs)
        return self.config.gymnasium_make_func(self.config.name, **self.config.kwargs, **kwargs)

    def _pred_space_discrete(self):
        # 実際に値を取得して予測
        done = True
        for _ in range(self.config.gym_prediction_step):
            if done:
                state, _ = self.env.reset()
                done = False
            else:
                action = self.env.action_space.sample()
                state, reward, terminated, truncated, info = self.env.step(action)
                done = terminated or truncated
            enc_state = space_encode_from_gym_to_srl(self.env.observation_space, state)
            if isinstance(enc_state, list):
                for e in enc_state:
                    if "int" not in str(np.asarray(e).dtype):
                        return False
            else:
                if "int" not in str(np.asarray(enc_state).dtype):
                    return False

        return True

    # --------------------------------
    # implement
    # --------------------------------

    @property
    def action_space(self) -> SpaceBase:
        return self._action_space

    @property
    def observation_space(self) -> SpaceBase:
        return self._observation_space

    @property
    def observation_type(self) -> EnvObservationTypes:
        return self._observation_type

    @property
    def max_episode_steps(self) -> int:
        if hasattr(self.env, "_max_episode_steps"):
            return getattr(self.env, "_max_episode_steps")
        elif hasattr(self.env, "spec"):
            if self.env.spec is not None and self.env.spec.max_episode_steps is not None:
                return self.env.spec.max_episode_steps
        return 99_999

    @property
    def player_num(self) -> int:
        return 1

    @property
    def next_player_index(self) -> int:
        return 0

    def reset(self) -> Tuple[np.ndarray, dict]:
        if self.seed is None:
            state, info = self.env.reset()
        else:
            # seed を最初のみ設定
            state, info = self.env.reset(seed=self.seed)
            self.env.action_space.seed(self.seed)
            self.env.observation_space.seed(self.seed)
            self.seed = None

        # wrapper
        for w in self.config.gym_wrappers:
            state = w.observation(state, self.env)

        # flatten
        if self.enable_flatten_observation:
            state = space_encode_from_gym_to_srl(self.env.observation_space, state)

        state = self.observation_space.sanitize(state)
        return state, info

    def step(self, action: EnvActionType) -> Tuple[np.ndarray, List[float], Union[bool, DoneTypes], InfoType]:
        # wrapper
        for w in self.config.gym_wrappers:
            action = w.action(action, self.env)

        # flatten
        if self.enable_flatten_action:
            action = space_decode_to_srl_from_gym(self.env.action_space, self.action_space, action)

        # step
        state, reward, terminated, truncated, info = self.env.step(action)
        if terminated:
            done = DoneTypes.TERMINATED
        elif truncated:
            done = DoneTypes.TRUNCATED
        else:
            done = DoneTypes.NONE

        # wrapper
        for w in self.config.gym_wrappers:
            state = w.observation(state, self.env)
            reward = w.reward(cast(float, reward), self.env)
            done = w.done(cast(DoneTypes, done), self.env)

        # flatten
        if self.enable_flatten_observation:
            state = space_encode_from_gym_to_srl(self.env.observation_space, state)

        state = self.observation_space.sanitize(state)
        return state, [float(reward)], done, info

    def close(self) -> None:
        self.env.close()

    @property
    def unwrapped(self) -> object:
        return self.env

    def set_seed(self, seed: Optional[int] = None) -> None:
        self.seed = seed

    @property
    def render_interval(self) -> float:
        return 1000 / self.fps

    def set_render_terminal_mode(self) -> None:
        # modeが違っていたら作り直す
        if self.render_mode != RenderModes.terminal and "ansi" in self.render_modes:
            try:
                self.env.close()
            except Exception as e:
                logger.warning(e)
            self.env = self.make_gymnasium_env(render_mode="ansi")
            self.render_mode = RenderModes.terminal

    def set_render_rgb_mode(self) -> None:
        # modeが違っていたら作り直す
        if self.render_mode != RenderModes.rgb_array and "rgb_array" in self.render_modes:
            try:
                self.env.close()
            except Exception as e:
                logger.warning(e)
            self.env = self.make_gymnasium_env(render_mode="rgb_array")
            self.render_mode = RenderModes.rgb_array

    def render_terminal(self, **kwargs) -> None:
        if self.render_mode == RenderModes.terminal:
            print(self.env.render(**kwargs))

    def render_rgb_array(self, **kwargs) -> Optional[np.ndarray]:
        if self.render_mode == RenderModes.rgb_array:
            return np.asarray(self.env.render(**kwargs))
        return None
