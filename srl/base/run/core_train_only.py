import logging
import time
from dataclasses import dataclass
from typing import Any, List

from srl.base.context import RunContext
from srl.base.rl.memory import IRLMemoryTrainer
from srl.base.rl.parameter import RLParameter
from srl.base.rl.trainer import RLTrainer
from srl.utils import common
from srl.utils.serialize import convert_for_json

from .callback import TrainerCallback

logger = logging.getLogger(__name__)


@dataclass
class RunStateTrainer:
    trainer: RLTrainer
    memory: IRLMemoryTrainer
    parameter: RLParameter

    elapsed_t0: float = 0
    end_reason: str = ""

    # train
    is_step_trained: bool = False

    # distributed
    sync_trainer: int = 0
    trainer_recv_q: int = 0

    def to_dict(self) -> dict:
        dat: dict = convert_for_json(self.__dict__)
        return dat


def play_trainer_only(
    context: RunContext,
    trainer: RLTrainer,
    callbacks: List[TrainerCallback] = [],
):
    assert context.training
    assert context.max_train_count > 0 or context.timeout > 0, "Please specify 'max_train_count' or 'timeout'."

    # --- play tf
    if context.enable_tf_device and context.framework == "tensorflow":
        if common.is_enable_tf_device_name(context.used_device_tf):
            import tensorflow as tf

            logger.info(f"tf.device({context.used_device_tf})")
            with tf.device(context.used_device_tf):  # type: ignore
                return _play_trainer_only(context, trainer, callbacks)
    return _play_trainer_only(context, trainer, callbacks)


def _play_trainer_only(
    context: RunContext,
    trainer: RLTrainer,
    callbacks: List[TrainerCallback],
):
    state = RunStateTrainer(trainer, trainer.memory, trainer.parameter)

    # --- 1 start
    state.trainer.train_start(context)

    # 2 callbacks
    _calls_on_trainer_loop: List[Any] = [c for c in callbacks if hasattr(c, "on_trainer_loop")]
    [c.on_trainer_start(context, state) for c in callbacks]

    # --- 3 init
    state.elapsed_t0 = time.time()

    # --- 4 loop
    logger.info("loop start")
    while True:
        _time = time.time()

        # --- stop check
        if context.timeout > 0 and (_time - state.elapsed_t0) >= context.timeout:
            state.end_reason = "timeout."
            break

        if context.max_train_count > 0 and state.trainer.get_train_count() >= context.max_train_count:
            state.end_reason = "max_train_count over."
            break

        # --- train
        state.is_step_trained = state.trainer.core_train()

        # callbacks
        _stop_flags = [c.on_trainer_loop(context, state) for c in _calls_on_trainer_loop]
        if True in _stop_flags:
            state.end_reason = "callback.trainer_intermediate_stop"
            break

    logger.info(f"loop end({state.end_reason})")

    # 5 end
    state.trainer.train_end()

    # 6 callbacks
    [c.on_trainer_end(context, state) for c in callbacks]
    return state
