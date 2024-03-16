from dataclasses import dataclass
from typing import Optional, Tuple

from srl.base.define import EnvTypes
from srl.base.exception import UndefinedError
from srl.base.rl.processor import ObservationProcessor
from srl.rl.processors.image_processor import ImageProcessor


@dataclass
class ImageBlockConfig:
    def __post_init__(self):
        self._name: str = ""
        self._kwargs: dict = {}
        self._processor: Optional[ObservationProcessor] = None

        self.set_dqn_block()

    def set_dqn_block(
        self,
        image_type: EnvTypes = EnvTypes.GRAY_2ch,
        resize: Tuple[int, int] = (84, 84),
        filters: int = 32,
        activation: str = "relu",
    ):
        """画像の入力に対してDQNで採用されたLayersを使用します。

        Args:
            image_type (EnvTypes): 画像のタイプ. Defaults to EnvTypes.GRAY_2ch
            resize (Tuple[int, int]): 画像のサイズ. Defaults to (84, 84)
            filters (int): 基準となるfilterの数です. Defaults to 32.
            activation (str): activation function. Defaults to "relu".
        """
        self._name = "DQN"
        self._kwargs = dict(filters=filters, activation=activation)
        self._processor = ImageProcessor(image_type, resize, enable_norm=True)

    def set_r2d3_block(
        self,
        image_type: EnvTypes = EnvTypes.COLOR,
        resize: Tuple[int, int] = (96, 72),
        filters: int = 16,
        activation: str = "relu",
    ):
        """画像の入力に対してR2D3で採用されたLayersを使用します。

        Args:
            image_type (EnvTypes): 画像のタイプ. Defaults to EnvTypes.COLOR
            resize (Tuple[int, int]): 画像のサイズ. Defaults to (96, 72)
            filters (int, optional): 基準となるfilterの数です. Defaults to 32.
            activation (str, optional): activation function. Defaults to "relu".
        """
        self._name = "R2D3"
        self._kwargs = dict(filters=filters, activation=activation)
        self._processor = ImageProcessor(image_type, resize, enable_norm=True)

    def set_alphazero_block(
        self,
        n_blocks: int = 19,
        filters: int = 256,
        activation: str = "relu",
    ):
        """Alphaシリーズの画像レイヤーで使用する層を指定します。
        AlphaZeroで採用されている層です。

        Args:
            n_blocks (int, optional): ブロック数. Defaults to 19.
            filters (int, optional): フィルター数. Defaults to 256.
            activation (str, optional): activation function. Defaults to "relu".
        """
        self._name = "AlphaZero"
        self._kwargs = dict(
            n_blocks=n_blocks,
            filters=filters,
            activation=activation,
        )
        self._processor = None

    def set_muzero_atari_block(
        self,
        image_type: EnvTypes = EnvTypes.GRAY_2ch,
        resize: Tuple[int, int] = (96, 96),
        filters: int = 128,
        activation: str = "relu",
        use_layer_normalization: bool = False,
    ):
        """Alphaシリーズの画像レイヤーで使用する層を指定します。
        MuZeroのAtari環境で採用されている層です。

        Args:
            filters (int, optional): フィルター数. Defaults to 128.
            activation (str, optional): activation function. Defaults to "relu".
            use_layer_normalization (str, optional): use_layer_normalization. Defaults to True.
        """
        self._name = "MuzeroAtari"
        self._kwargs = dict(
            filters=filters,
            activation=activation,
            use_layer_normalization=use_layer_normalization,
        )
        self._processor = ImageProcessor(image_type, resize, enable_norm=True)

    def set_custom_block(self, entry_point: str, kwargs: dict, processor: Optional[ObservationProcessor] = None):
        self._name = "custom"
        self._kwargs = dict(entry_point=entry_point, kwargs=kwargs)
        self._processor = processor

    # ----------------------------------------------------------------

    def get_processor(self) -> Optional[ObservationProcessor]:
        return self._processor

    def create_block_tf(self, enable_time_distributed_layer: bool = False):
        if self._name == "DQN":
            from .tf import dqn_image_block

            return dqn_image_block.DQNImageBlock(**self._kwargs)
        if self._name == "R2D3":
            from .tf import r2d3_image_block

            return r2d3_image_block.R2D3ImageBlock(
                enable_time_distributed_layer=enable_time_distributed_layer,
                **self._kwargs,
            )
        if self._name == "AlphaZero":
            from .tf.alphazero_image_block import AlphaZeroImageBlock

            return AlphaZeroImageBlock(**self._kwargs)
        if self._name == "MuzeroAtari":
            from .tf.muzero_atari_block import MuZeroAtariBlock

            return MuZeroAtariBlock(**self._kwargs)

        if self._name == "custom":
            from srl.utils.common import load_module

            return load_module(self._kwargs["entry_point"])(
                enable_time_distributed_layer=enable_time_distributed_layer,
                **self._kwargs["kwargs"],
            )

        raise UndefinedError(self._name)

    def create_block_torch(
        self,
        in_shape: Tuple[int, ...],
        enable_time_distributed_layer: bool = False,
    ):
        if self._name == "DQN":
            from .torch_ import dqn_image_block

            return dqn_image_block.DQNImageBlock(
                in_shape,
                enable_time_distributed_layer=enable_time_distributed_layer,
                **self._kwargs,
            )
        if self._name == "R2D3":
            from .torch_ import r2d3_image_block

            return r2d3_image_block.R2D3ImageBlock(
                in_shape,
                enable_time_distributed_layer=enable_time_distributed_layer,
                **self._kwargs,
            )

        if self._name == "AlphaZero":
            from .torch_.alphazero_image_block import AlphaZeroImageBlock

            return AlphaZeroImageBlock(in_shape, **self._kwargs)
        if self._name == "MuzeroAtari":
            from .torch_.muzero_atari_block import MuZeroAtariBlock

            return MuZeroAtariBlock(in_shape, **self._kwargs)

        if self._name == "custom":
            from srl.utils.common import load_module

            return load_module(self._kwargs["entry_point"])(**self._kwargs["kwargs"])

        raise UndefinedError(self._name)
