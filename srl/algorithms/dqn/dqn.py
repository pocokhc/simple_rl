import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, cast

import numpy as np

from srl.base.define import RLBaseTypes
from srl.base.rl.algorithms.discrete_action import DiscreteActionWorker
from srl.base.rl.base import RLParameter
from srl.base.rl.config import RLConfig
from srl.base.rl.processor import ObservationProcessor
from srl.rl.functions.common import (
    create_epsilon_list,
    create_fancy_index_for_invalid_actions,
    inverse_rescaling,
    render_discrete_action,
    rescaling,
)
from srl.rl.memories.experience_replay_buffer import ExperienceReplayBuffer, ExperienceReplayBufferConfig
from srl.rl.models.framework_config import FrameworkConfig
from srl.rl.models.image_block import ImageBlockConfig
from srl.rl.models.mlp_block import MLPBlockConfig
from srl.rl.schedulers.scheduler import SchedulerConfig

"""
Paper
・Playing Atari with Deep Reinforcement Learning
https://arxiv.org/pdf/1312.5602.pdf

・Human-level control through deep reinforcement learning
https://www.nature.com/articles/nature14236


window_length          : -
Fixed Target Q-Network : o
Error clipping     : o
Experience Replay  : o
Frame skip         : -
Annealing e-greedy : o (config selection)
Reward clip        : o (config selection)
Image preprocessor : -

Other
    Double DQN                 : o (config selection)
    Priority Experience Replay : o (config selection)
    Value function rescaling   : o (config selection)
    invalid_actions            : o
"""


# ------------------------------------------------------
# config
# ------------------------------------------------------
@dataclass
class Config(RLConfig, ExperienceReplayBufferConfig):
    """<:ref:`ExperienceReplayBuffer`>"""

    #: ε-greedy parameter for Test
    test_epsilon: float = 0

    #: Learning rate during distributed learning
    #: :math:`\epsilon_i = \epsilon^{1 + \frac{i}{N-1} \alpha}`
    actor_epsilon: float = 0.4
    #: Look actor_epsilon
    actor_alpha: float = 7.0

    #: <:ref:`scheduler`> ε-greedy parameter for Train
    epsilon: float = 0.1  # type: ignore , type OK
    #: <:ref:`scheduler`> Learning rate
    lr: float = 0.001  # type: ignore , type OK

    #: Discount rate
    discount: float = 0.99
    #: Synchronization interval to Target network
    target_model_update_interval: int = 1000
    #: If True, clip the reward to three types [-1,0,1]
    enable_reward_clip: bool = False

    #: enable DoubleDQN
    enable_double_dqn: bool = True
    #: enable rescaling
    enable_rescale: bool = False

    #: <:ref:`Framework`>
    framework: FrameworkConfig = field(init=False, default_factory=lambda: FrameworkConfig())
    #: <:ref:`MLPBlock`> This layer is only used when the input is an value.
    input_value_block: MLPBlockConfig = field(init=False, default_factory=lambda: MLPBlockConfig())
    #: <:ref:`ImageBlock`> This layer is only used when the input is an image.
    input_image_block: ImageBlockConfig = field(init=False, default_factory=lambda: ImageBlockConfig())
    #: <:ref:`MLPBlock`> hidden layer
    hidden_block: MLPBlockConfig = field(init=False, default_factory=lambda: MLPBlockConfig())

    def __post_init__(self):
        super().__post_init__()

        self.epsilon: SchedulerConfig = SchedulerConfig(cast(float, self.epsilon))
        self.lr: SchedulerConfig = SchedulerConfig(cast(float, self.lr))

    def set_config_by_actor(self, actor_num: int, actor_id: int) -> None:
        e = create_epsilon_list(actor_num, epsilon=self.actor_epsilon, alpha=self.actor_alpha)[actor_id]
        self.epsilon.set_constant(e)

    def set_atari_config(self):
        """Set the Atari parameters written in the paper."""
        self.batch_size = 32
        self.memory.capacity = 1_000_000
        self.memory.warmup_size = 50_000
        self.input_image_block.set_dqn_base()
        self.hidden_block.set_mlp((512,))
        self.target_model_update_interval = 10000
        self.discount = 0.99
        self.lr.set_constant(0.00025)
        self.epsilon.set_linear(1_000_000, 1.0, 0.1)

        self.enable_reward_clip = True
        self.enable_double_dqn = False
        self.enable_rescale = False

    # -------------------------------

    def get_processors(self) -> List[Optional[ObservationProcessor]]:
        return [self.input_image_block.get_processor()]

    def get_base_action_type(self) -> RLBaseTypes:
        return RLBaseTypes.DISCRETE

    def get_base_observation_type(self) -> RLBaseTypes:
        return RLBaseTypes.CONTINUOUS

    def get_use_framework(self) -> str:
        return self.framework.get_use_framework()

    def getName(self) -> str:
        return f"DQN:{self.get_use_framework()}"

    def assert_params(self) -> None:
        super().assert_params()
        self.assert_params_memory()

    def get_info_types(self) -> dict:
        return {
            "loss": {"data": "ave"},
            "sync": {"type": int, "data": "last"},
            "epsilon": {"data": "last"},
            "lr": {"data": "last"},
        }


# ------------------------------------------------------
# Memory
# ------------------------------------------------------
class Memory(ExperienceReplayBuffer):
    pass


# ------------------------------------------------------
# Parameter
# ------------------------------------------------------
class CommonInterfaceParameter(RLParameter, ABC):
    def __init__(self, *args):
        super().__init__(*args)
        self.config: Config = self.config

    @abstractmethod
    def create_batch_data(self, state):
        raise NotImplementedError()

    @abstractmethod
    def predict_q(self, state) -> np.ndarray:
        raise NotImplementedError()

    @abstractmethod
    def predict_target_q(self, state) -> np.ndarray:
        raise NotImplementedError()

    def calc_target_q(
        self,
        batch_size,
        n_state,
        reward,
        done,
        next_invalid_actions,
    ):
        # ここの計算はtfで計算するよりnpで計算したほうが早い

        n_inv_act_idx1, n_inv_act_idx2 = create_fancy_index_for_invalid_actions(next_invalid_actions)

        n_q_target = self.predict_target_q(n_state)

        # DoubleDQN: indexはonlineQから選び、値はtargetQを選ぶ
        if self.config.enable_double_dqn:
            n_q = self.predict_q(n_state)
            n_q[n_inv_act_idx1, n_inv_act_idx2] = np.min(n_q)
            n_act_idx = np.argmax(n_q, axis=1)
            maxq = n_q_target[np.arange(batch_size), n_act_idx]
        else:
            n_q_target[n_inv_act_idx1, n_inv_act_idx2] = np.min(n_q_target)
            maxq = np.max(n_q_target, axis=1)

        if self.config.enable_rescale:
            maxq = inverse_rescaling(maxq)

        # --- Q値を計算
        target_q = reward + done * self.config.discount * maxq

        if self.config.enable_rescale:
            target_q = rescaling(target_q)

        return target_q.astype(np.float32)


# ------------------------------------------------------
# Worker
# ------------------------------------------------------
class Worker(DiscreteActionWorker):
    def __init__(self, *args):
        super().__init__(*args)
        self.config: Config = self.config
        self.parameter: CommonInterfaceParameter = self.parameter

        self.epsilon_sch = self.config.epsilon.create_schedulers()

    def call_on_reset(self, state: np.ndarray, invalid_actions: List[int]) -> dict:
        return {}

    def call_policy(self, state: np.ndarray, invalid_actions: List[int]) -> Tuple[int, dict]:
        self.state = state

        if self.training:
            epsilon = self.epsilon_sch.get_and_update_rate(self.total_step)
        else:
            epsilon = self.config.test_epsilon

        if random.random() < epsilon:
            # epsilonより低いならランダム
            self.action = random.choice([a for a in range(self.config.action_num) if a not in invalid_actions])
            self.q = None
        else:
            state = self.parameter.create_batch_data(state)
            self.q = self.parameter.predict_q(state)[0]
            self.q[invalid_actions] = -np.inf

            # 最大値を選ぶ（複数はほぼないので無視）
            self.action = int(np.argmax(self.q))

        return self.action, {"epsilon": epsilon}

    def call_on_step(
        self,
        next_state: np.ndarray,
        reward: float,
        done: bool,
        next_invalid_actions: List[int],
    ):
        if not self.training:
            return {}

        # reward clip
        if self.config.enable_reward_clip:
            if reward < 0:
                reward = -1
            elif reward > 0:
                reward = 1
            else:
                reward = 0

        """
        [
            state,
            n_state,
            onehot_action,
            reward,
            done,
            next_invalid_actions,
        ]
        """
        self.memory.add(
            [
                self.state,
                next_state,
                np.identity(self.config.action_num, dtype=int)[self.action],
                reward,
                int(not done),
                next_invalid_actions,
            ]
        )
        return {}

    def render_terminal(self, worker, **kwargs) -> None:
        if self.q is None:
            state = self.parameter.create_batch_data(self.state)
            q = self.parameter.predict_q(state)[0]
        else:
            q = self.q
        maxa = np.argmax(q)
        if self.config.enable_rescale:
            q = inverse_rescaling(q)

        def _render_sub(a: int) -> str:
            return f"{q[a]:7.5f}"

        render_discrete_action(maxa, worker.env, self.config, _render_sub)
