import datetime
import glob
import logging
import os
import time
import traceback
from dataclasses import dataclass

from srl.base.run.callback import RunCallback, TrainerCallback
from srl.base.run.context import RunContext
from srl.base.run.core import RunState
from srl.runner.callback import RunnerCallback
from srl.runner.callbacks.evaluate import Evaluate
from srl.runner.runner import Runner

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint(RunnerCallback, RunCallback, TrainerCallback, Evaluate):
    save_dir: str = "checkpoints"
    interval: int = 60 * 20  # s

    @staticmethod
    def get_parameter_path(save_dir: str) -> str:
        # 最後のpathを取得
        trains = []
        for f in glob.glob(os.path.join(save_dir, "*.pickle")):
            try:
                date = os.path.basename(f).split("_")[0]
                date = datetime.datetime.strptime(date, "%Y%m%d-%H%M%S")
                trains.append([date, f])
            except Exception:
                logger.warning(traceback.format_exc())
        if len(trains) == 0:
            return ""
        trains.sort()
        return trains[-1][1]

    def on_runner_start(self, runner: Runner) -> None:
        if not os.path.isdir(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)
            logger.info(f"makedirs: {self.save_dir}")

    def _save_parameter(self, state: RunState, is_last: bool):
        if state.trainer is None:
            return
        if state.parameter is None:
            return
        train_count = state.trainer.get_train_count()

        if self.enable_eval:
            eval_rewards = self.run_eval(state.parameter)
        else:
            eval_rewards = "None"

        fn = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        fn += f"_{train_count}_{eval_rewards}"
        if is_last:
            fn += "_last"
        fn += ".pickle"

        state.parameter.save(os.path.join(self.save_dir, fn))

    # ---------------------------
    # actor
    # ---------------------------
    def on_episodes_begin(self, context: RunContext, state: RunState):
        # Trainerがいる場合のみ保存
        if state.trainer is None:
            return

        # eval
        if self.runner is not None:
            self.setup_eval_runner(self.runner)

        self.interval_t0 = time.time()
        self._save_parameter(state, is_last=False)

    def on_episode_end(self, context: RunContext, state: RunState):
        if state.trainer is None:
            return
        if time.time() - self.interval_t0 > self.interval:
            self._save_parameter(state, is_last=False)
            self.interval_t0 = time.time()

    def on_episodes_end(self, context: RunContext, state: RunState) -> None:
        if state.trainer is None:
            return
        self._save_parameter(state, is_last=True)

    # ---------------------------
    # trainer
    # ---------------------------
    def on_trainer_start(self, context: RunContext, state: RunState):
        # eval
        if self.runner is not None:
            self.setup_eval_runner(self.runner)

        self.interval_t0 = time.time()
        self._save_parameter(state, is_last=False)

    def on_trainer_loop(self, context: RunContext, state: RunState):
        if time.time() - self.interval_t0 > self.interval:
            self._save_parameter(state, is_last=False)
            self.interval_t0 = time.time()

    def on_trainer_end(self, context: RunContext, state: RunState):
        self._save_parameter(state, is_last=True)
