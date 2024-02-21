import math
import random
from pprint import pprint
from typing import Any, Optional, Tuple

import numpy as np
import pytest

import srl
from srl.base import spaces as srl_spaces
from srl.base.define import EnvObservationTypes, RLTypes
from srl.base.env.gym_user_wrapper import GymUserWrapper
from srl.base.spaces.space import SpaceBase
from srl.test import TestEnv


def test_play_FrozenLake():
    pytest.importorskip("gym")

    # observation_space: Discrete(16)
    # action_space     : Discrete(4)
    tester = TestEnv()
    env = tester.play_test("FrozenLake-v1", env_config_kwargs={"use_gym": True}, check_render=False, check_restore=False)
    assert env.observation_type == EnvObservationTypes.DISCRETE
    assert env.observation_space == srl_spaces.DiscreteSpace(16)
    assert env.action_space == srl_spaces.DiscreteSpace(4)


def test_play_CartPole():
    pytest.importorskip("gym")

    # observation_space: Box((4,))
    # action_space     : Discrete(2)
    tester = TestEnv()
    env = tester.play_test("CartPole-v1", max_step=10, env_config_kwargs={"use_gym": True}, check_render=False, check_restore=False)
    assert env.observation_type == EnvObservationTypes.CONTINUOUS
    assert env.observation_space.shape == srl_spaces.BoxSpace((4,)).shape  # range skip
    assert env.action_space == srl_spaces.DiscreteSpace(2)


def test_play_Blackjack():
    pytest.importorskip("gym")

    # observation_space: Tuple(Discrete(32), Discrete(11), Discrete(2))
    # action_space     : Discrete(2)
    tester = TestEnv()
    env = tester.play_test("Blackjack-v1", max_step=10, env_config_kwargs={"use_gym": True}, check_render=False, check_restore=False)
    assert env.observation_type == EnvObservationTypes.DISCRETE
    assert env.observation_space == srl_spaces.ArraySpace(
        [
            srl_spaces.DiscreteSpace(32),
            srl_spaces.DiscreteSpace(11),
            srl_spaces.DiscreteSpace(2),
        ]
    )
    assert env.action_space == srl_spaces.DiscreteSpace(2)


def test_play_Pendulum():
    pytest.importorskip("gym")

    # observation_space: Box([-1. -1. -8.], [1. 1. 8.], (3,), float32)
    # action_space     : Box(-2.0, 2.0, (1,), float32)
    tester = TestEnv()
    env = tester.play_test("Pendulum-v1", max_step=10, env_config_kwargs={"use_gym": True}, check_render=False, check_restore=False)
    assert env.observation_type == EnvObservationTypes.CONTINUOUS
    assert env.observation_space == srl_spaces.BoxSpace((3,), [-1, -1, -8], [1, 1, 8])
    assert env.action_space == srl_spaces.BoxSpace((1,), -2.0, 2.0)


def test_play_Tetris():
    pytest.importorskip("gym")
    pytest.importorskip("ale_py")

    # Box(0, 255, (210, 160, 3), uint8)
    # Discrete(5)
    tester = TestEnv()
    env = tester.play_test("ALE/Tetris-v5", check_render=False, max_step=10, env_config_kwargs={"use_gym": True}, check_restore=False)
    assert env.observation_type == EnvObservationTypes.COLOR
    assert env.observation_space == srl_spaces.BoxSpace((210, 160, 3), 0, 255, np.uint8)
    assert env.action_space == srl_spaces.DiscreteSpace(5)


def test_play_Tetris_ram():
    pytest.importorskip("gym")
    pytest.importorskip("ale_py")

    # Box(0, 255, (128,), uint8)
    # Discrete(5)
    tester = TestEnv()
    env = tester.play_test("ALE/Tetris-ram-v5", check_render=False, max_step=10, env_config_kwargs={"use_gym": True}, check_restore=False)
    assert env.observation_type == EnvObservationTypes.DISCRETE
    assert env.observation_space == srl_spaces.BoxSpace((128,), 0, 255, np.uint8)
    assert env.action_space == srl_spaces.DiscreteSpace(5)


# 時間がかかる割に有益じゃないのでコメントアウト
# def test_play_all(self):
#     import gym
#     import gym.error
#     from gym import envs
#     from tqdm import tqdm
#
#     specs = envs.registry.all()
#
#     for spec in tqdm(list(reversed(list(specs)))):
#         try:
#             gym.make(spec.id)
#             self.tester.play_test(spec.id, check_render=False, max_step=5)
#         except AttributeError:
#             pass
#         except gym.error.DependencyNotInstalled:
#             pass  # No module named 'mujoco_py'
#         except ModuleNotFoundError:
#             pass  # unsupported env
#         except Exception:
#             print(spec.id)
#             raise

# --------------------------------


def test_space():
    pytest.importorskip("gym")

    from gym import spaces

    from srl.base.env.gym_wrapper import (space_change_from_gym_to_srl,
                                          space_decode_to_srl_from_gym,
                                          space_encode_from_gym_to_srl)

    space = spaces.Dict(
        {
            "ext_controller": spaces.MultiDiscrete([5, 2, 2]),
            "inner_state": spaces.Dict(
                {
                    "charge": spaces.Discrete(100),
                    "system_checks": spaces.MultiBinary(10),
                    "job_status": spaces.Dict(
                        {
                            "task": spaces.Discrete(5),
                            "progress": spaces.Box(low=0, high=100, shape=()),
                        }
                    ),
                }
            ),
            "other": spaces.Tuple(
                [
                    spaces.Discrete(7),
                    spaces.Box(low=0, high=10, shape=(2, 3)),
                ]
            ),
        }
    )

    srl_space = space_change_from_gym_to_srl(space)
    print(srl_space)
    assert srl_space.rl_type == RLTypes.CONTINUOUS
    assert isinstance(srl_space, srl_spaces.ArraySpace)
    assert len(srl_space.spaces) == 7

    assert isinstance(srl_space.spaces[0], srl_spaces.BoxSpace)
    assert srl_space.spaces[0].shape == (3,)
    assert (srl_space.spaces[0].low == (0, 0, 0)).all()
    assert (srl_space.spaces[0].high == (5, 2, 2)).all()
    assert srl_space.spaces[0]._dtype == np.int64

    assert isinstance(srl_space.spaces[1], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[1].n == 100

    assert isinstance(srl_space.spaces[2], srl_spaces.BoxSpace)
    assert srl_space.spaces[2].shape == ()
    assert srl_space.spaces[2]._dtype == np.float32

    assert isinstance(srl_space.spaces[3], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[3].n == 5

    assert isinstance(srl_space.spaces[4], srl_spaces.BoxSpace)
    assert srl_space.spaces[4].shape == (10,)
    assert (srl_space.spaces[4].low == (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)).all()
    assert (srl_space.spaces[4].high == (1, 1, 1, 1, 1, 1, 1, 1, 1, 1)).all()
    assert srl_space.spaces[4]._dtype == np.int8

    assert isinstance(srl_space.spaces[5], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[5].n == 7

    assert isinstance(srl_space.spaces[6], srl_spaces.BoxSpace)
    assert srl_space.spaces[6].shape == (2, 3)
    assert srl_space.spaces[6]._dtype == np.float32

    val = space.sample()
    print(val)

    encode_val = space_encode_from_gym_to_srl(space, val)
    print("----")
    pprint(encode_val)
    assert isinstance(encode_val, list)
    assert len(encode_val) == 7

    decode_val = space_decode_to_srl_from_gym(space, srl_space, encode_val)
    print("----")
    pprint(decode_val)

    assert (val["ext_controller"] == decode_val["ext_controller"]).all()
    assert val["inner_state"]["charge"] == decode_val["inner_state"]["charge"]
    assert val["inner_state"]["job_status"]["progress"] == decode_val["inner_state"]["job_status"]["progress"]
    assert val["inner_state"]["job_status"]["task"] == decode_val["inner_state"]["job_status"]["task"]
    assert (val["inner_state"]["system_checks"] == decode_val["inner_state"]["system_checks"]).all()
    assert val["other"][0] == decode_val["other"][0]
    assert (val["other"][1] == decode_val["other"][1]).all()

    # ---------------------
    val = {
        "ext_controller": [3, 0, 0],
        "inner_state": {
            "charge": 68,
            "job_status": {
                "progress": [73.78551],
                "task": 4,
            },
            "system_checks": [0, 0, 1, 0, 0, 0, 1, 1, 1, 0],
        },
        "other": [6, [[3.1046488, 5.9139466, 4.120618], [8.221998, 4.1012044, 7.6347136]]],
    }
    encode_val = space_encode_from_gym_to_srl(space, val)
    print("----")
    pprint(encode_val)
    assert isinstance(encode_val, list)
    assert len(encode_val) == 7
    assert (encode_val[0] == [3, 0, 0]).all()
    assert encode_val[1] == 68
    assert (encode_val[2] == np.array([73.78551], np.float32)).all()
    assert encode_val[3] == 4
    assert (encode_val[4] == [0, 0, 1, 0, 0, 0, 1, 1, 1, 0]).all()
    assert encode_val[5] == 6
    assert (
        encode_val[6] == np.array([[3.1046488, 5.9139466, 4.120618], [8.221998, 4.1012044, 7.6347136]], np.float32)
    ).all()

    decode_val = space_decode_to_srl_from_gym(space, srl_space, encode_val)
    print("----")
    pprint(decode_val)


def test_space_discrete():
    pytest.importorskip("gym")

    from gym import spaces

    from srl.base.env.gym_wrapper import (space_change_from_gym_to_srl,
                                          space_decode_to_srl_from_gym,
                                          space_encode_from_gym_to_srl)

    space = spaces.Dict(
        {
            "ext_controller": spaces.MultiDiscrete([5, 2, 2]),
            "inner_state": spaces.Dict(
                {
                    "charge": spaces.Discrete(100),
                    "system_checks": spaces.MultiBinary([3, 2]),
                    "job_status": spaces.Dict(
                        {
                            "task": spaces.Discrete(5),
                        }
                    ),
                }
            ),
            "other": spaces.Tuple(
                [
                    spaces.Discrete(7),
                ]
            ),
        }
    )

    space = spaces.Dict(
        {
            "ext_controller": spaces.MultiDiscrete([5, 2, 2]),
            "inner_state": spaces.Dict(
                {
                    "charge": spaces.Discrete(100),
                    "system_checks": spaces.MultiBinary([3, 2]),
                    "job_status": spaces.Dict(
                        {
                            "task": spaces.Discrete(5),
                        }
                    ),
                }
            ),
            "other": spaces.Tuple(
                [
                    spaces.Discrete(7, start=1),
                ]
            ),
        }
    )

    srl_space = space_change_from_gym_to_srl(space)
    print(srl_space)
    assert srl_space.rl_type == RLTypes.DISCRETE
    assert isinstance(srl_space, srl_spaces.ArraySpace)
    assert len(srl_space.spaces) == 5

    assert isinstance(srl_space.spaces[0], srl_spaces.BoxSpace)
    assert srl_space.spaces[0].shape == (3,)
    assert (srl_space.spaces[0].low == (0, 0, 0)).all()
    assert (srl_space.spaces[0].high == (5, 2, 2)).all()
    assert srl_space.spaces[0]._dtype == np.int64

    assert isinstance(srl_space.spaces[1], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[1].n == 100

    assert isinstance(srl_space.spaces[2], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[2].n == 5

    assert isinstance(srl_space.spaces[3], srl_spaces.BoxSpace)
    assert srl_space.spaces[3].shape == (3, 2)
    assert srl_space.spaces[3]._dtype == np.int8

    assert isinstance(srl_space.spaces[4], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[4].n == 7
    assert srl_space.spaces[4]._start == 1

    val = space.sample()
    print(val)

    encode_val = space_encode_from_gym_to_srl(space, val)
    print(encode_val)
    assert len(encode_val) == 5

    decode_val = space_decode_to_srl_from_gym(space, srl_space, encode_val)
    print(decode_val)

    print(val["ext_controller"], decode_val["ext_controller"])
    assert (val["ext_controller"] == decode_val["ext_controller"]).all()
    assert val["inner_state"]["charge"] == decode_val["inner_state"]["charge"]
    assert val["inner_state"]["job_status"]["task"] == decode_val["inner_state"]["job_status"]["task"]
    assert (val["inner_state"]["system_checks"] == decode_val["inner_state"]["system_checks"]).all()
    assert val["other"][0] == decode_val["other"][0]


def test_original_space():
    pytest.importorskip("gym")

    from gym import spaces

    class MyStrSpace(spaces.Space[str]):
        def sample(self, mask=None):
            return "a"

    from srl.base.env.gym_wrapper import (space_change_from_gym_to_srl,
                                          space_decode_to_srl_from_gym,
                                          space_encode_from_gym_to_srl)

    # --- fail pattern
    with pytest.raises(AssertionError):
        space_change_from_gym_to_srl(MyStrSpace())

    # --- success pattern
    space = spaces.Dict(
        {
            "a_info": spaces.Discrete(2),
            "b_space": MyStrSpace(),
            "c_info": spaces.Discrete(3),
        }
    )
    srl_space = space_change_from_gym_to_srl(space)
    print(srl_space)
    assert srl_space.rl_type == RLTypes.DISCRETE
    assert isinstance(srl_space, srl_spaces.ArraySpace)
    assert len(srl_space.spaces) == 2

    assert isinstance(srl_space.spaces[0], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[0].n == 2

    assert isinstance(srl_space.spaces[1], srl_spaces.DiscreteSpace)
    assert srl_space.spaces[1].n == 3

    val = space.sample()
    print(val)

    encode_val = space_encode_from_gym_to_srl(space, val)
    print(encode_val)
    assert len(encode_val) == 2

    decode_val = space_decode_to_srl_from_gym(space, srl_space, encode_val)
    print(decode_val)

    assert val["a_info"] == decode_val["a_info"]
    assert val["c_info"] == decode_val["c_info"]


def test_random():
    pytest.importorskip("gym")

    env = srl.make_env(srl.EnvConfig("Pendulum-v1", use_gym=True))
    print(env.action_space)
    print(env.observation_space)

    seed = 1
    true_reward = -2.4091601371765137

    random.seed(seed)
    np.random.seed(seed)

    reward = 0
    env.reset(seed=seed)
    for _ in range(10):
        env.step(env.sample_action())
        reward += env.reward
    assert math.isclose(reward, true_reward)

    random.seed(seed)
    np.random.seed(seed)

    reward = 0
    env.reset(seed=seed)
    for _ in range(10):
        env.step(env.sample_action())
        reward += env.reward
    assert math.isclose(reward, true_reward)


def test_wrapper():
    pytest.importorskip("gym")
    import gym

    class MyWrapper(GymUserWrapper):
        def action_space(
            self,
            action_space: Optional[SpaceBase],
            env: gym.Env,
        ) -> Optional[SpaceBase]:
            return srl_spaces.DiscreteSpace(99)

        def action(self, action: Any, env: gym.Env) -> Any:
            return 0

        def observation_space(
            self,
            observation_type: EnvObservationTypes,
            observation_space: Optional[SpaceBase],
            env: gym.Env,
        ) -> Tuple[EnvObservationTypes, Optional[SpaceBase]]:
            return EnvObservationTypes.DISCRETE, srl_spaces.DiscreteSpace(99)

        def observation(self, observation: Any, env: gym.Env) -> Any:
            return 1

        def reward(self, reward: float, env: gym.Env) -> float:
            return 9

        def done(self, done: bool, env: gym.Env) -> bool:
            return True

    wrapper = MyWrapper()
    env_config = srl.EnvConfig("CliffWalking-v0", gym_wrappers=[wrapper], use_gym=True)
    env = srl.make_env(env_config)

    print(env.action_space)
    print(env.observation_space)
    assert isinstance(env.action_space, srl_spaces.DiscreteSpace)
    assert isinstance(env.observation_space, srl_spaces.DiscreteSpace)
    assert env.action_space.n == 99
    assert env.observation_space.n == 99

    env.reset(render_mode="terminal")
    assert env.state == 1
    while not env.done:
        env.step(None)
        assert env.state == 1
        assert env.reward == 9
        assert env.done
