import unittest

import srl
from srl.test import TestRL


class Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tester = TestRL()
        self.base_config = dict(
            lstm_units=32,
            hidden_layer_sizes=(16, 16),
            enable_dueling_network=False,
            memory_name="ReplayMemory",
            target_model_update_interval=100,
            enable_rescale=True,
            burnin=5,
            sequence_length=5,
            enable_retrace=False,
        )

    def test_sequence(self):
        self.tester.play_sequence(srl.rl.r2d2.Config())

    def test_mp(self):
        self.tester.play_mp(srl.rl.r2d2.Config())

    def test_verify_Pendulum(self):
        rl_config = srl.rl.r2d2.Config(**self.base_config)
        self.tester.play_verify_singleplay("Pendulum-v1", rl_config, 200 * 35)

    def test_verify_Pendulum_mp(self):
        rl_config = srl.rl.r2d2.Config(**self.base_config)
        self.tester.play_verify_singleplay("Pendulum-v1", rl_config, 200 * 20, is_mp=True)

    def test_verify_Pendulum_retrace(self):
        rl_config = srl.rl.r2d2.Config(**self.base_config)
        rl_config.enable_retrace = True
        self.tester.play_verify_singleplay("Pendulum-v1", rl_config, 200 * 35)

    def test_verify_Pendulum_memory(self):
        rl_config = srl.rl.r2d2.Config(**self.base_config)
        rl_config.memory_name = "ProportionalMemory"
        self.tester.play_verify_singleplay("Pendulum-v1", rl_config, 200 * 40)


if __name__ == "__main__":
    unittest.main(module=__name__, defaultTest="Test.test_verify_Pendulum_disable_int", verbosity=2)
