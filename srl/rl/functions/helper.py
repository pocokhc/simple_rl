import random
from typing import List, Optional, Tuple, Union

import numpy as np

from srl.base.define import SpaceTypes
from srl.base.env.env_run import EnvRun


def get_random_max_index(arr: Union[np.ndarray, List[float]], invalid_actions: List[int] = []) -> int:
    """Destructive to the original variable."""
    if len(arr) < 100:
        if len(invalid_actions) > 0:
            if isinstance(arr, np.ndarray):
                arr = arr.tolist()
            arr = arr[:]
            for a in invalid_actions:
                arr[a] = -np.inf
        max_value = max(arr)
        max_list = [i for i, val in enumerate(arr) if val == max_value]
        return max_list[0] if len(max_list) == 1 else random.choice(max_list)
    else:
        arr = np.asarray(arr, dtype=float)
        arr[invalid_actions] = -np.inf
        return random.choice(np.where(arr == arr.max())[0].tolist())


def random_choice_by_probs(probs, total=None):
    if total is None:
        total = sum(probs)
    r = random.random() * total

    num = 0
    for i, weight in enumerate(probs):
        num += weight
        if r <= num:
            return i

    raise ValueError(f"not coming. total: {total}, r: {r}, num: {num}, probs: {probs}")


def calc_epsilon_greedy_probs(q, invalid_actions, epsilon, action_num):
    # filter
    q = np.array([(-np.inf if a in invalid_actions else v) for a, v in enumerate(q)])

    q_max = np.amax(q, axis=0)
    q_max_num = np.count_nonzero(q == q_max)

    valid_action_num = action_num - len(invalid_actions)
    probs = []
    for a in range(action_num):
        if a in invalid_actions:
            probs.append(0.0)
        else:
            prob = epsilon / valid_action_num
            if q[a] == q_max:
                prob += (1 - epsilon) / q_max_num
            probs.append(prob)
    return probs


def render_discrete_action(maxa: int, action_num: int, env: EnvRun, func) -> None:
    invalid_actions = env.get_invalid_actions()
    for action in range(action_num):
        if action in invalid_actions:
            continue
        s = "*" if action == maxa else " "
        rl_s = func(action)
        s += f"{env.action_to_str(action):3s}: {rl_s}"
        print(s)

    # invalid actions
    view_invalid_actions_num = 0
    for action in range(action_num):
        if action not in invalid_actions:
            continue
        if view_invalid_actions_num > 2:
            continue
        s = "x"
        view_invalid_actions_num += 1
        rl_s = func(action)
        s += f"{env.action_to_str(action):3s}: {rl_s}"
        print(s)
    if view_invalid_actions_num > 2:
        print("... Some invalid actions have been omitted.")


def create_fancy_index_for_invalid_actions(idx_list: List[List[int]]):
    """ファンシーインデックス
    idx_list = [
        [1, 2, 5],
        [2],
        [2, 3],
    ]
    idx1 = [0, 0, 0, 1, 2, 2]
    idx2 = [1, 2, 5, 2, 2, 3]
    """
    idx1 = [i for i, sublist in enumerate(idx_list) for _ in sublist]
    idx2 = [item for sublist in idx_list for item in sublist]
    return idx1, idx2


def one_hot(x, size: int, dtype=np.float32):
    x = np.asarray(x)
    return np.identity(size, dtype=dtype)[x]


def image_processor(
    rgb_array: np.ndarray,  # (H,W,C)
    from_space_type: SpaceTypes,
    to_space_type: SpaceTypes,
    resize: Optional[Tuple[int, int]] = None,  # resize: (w, h)
    trimming: Optional[Tuple[int, int, int, int]] = None,  # (top, left, bottom, right)
    shape_order: str = "HWC",  # "HWC": tf(H,W,C), "CHW": torch(C,H,W)
):
    assert from_space_type in [
        SpaceTypes.GRAY_2ch,
        SpaceTypes.GRAY_3ch,
        SpaceTypes.COLOR,
    ]
    import cv2

    if to_space_type == SpaceTypes.COLOR and (
        from_space_type == SpaceTypes.GRAY_2ch or from_space_type == SpaceTypes.GRAY_3ch
    ):
        # gray -> color
        rgb_array = cv2.applyColorMap(rgb_array, cv2.COLORMAP_HOT)
    elif from_space_type == SpaceTypes.COLOR and (
        to_space_type == SpaceTypes.GRAY_2ch or to_space_type == SpaceTypes.GRAY_3ch
    ):
        # color -> gray
        rgb_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)

    if trimming is not None:
        top, left, bottom, right = trimming
        assert top < bottom
        assert left < right
        w = rgb_array.shape[1]
        h = rgb_array.shape[0]
        if top < 0:
            top = 0
        if left < 0:
            left = 0
        if bottom > h:
            bottom = h
        if right > w:
            right = w
        rgb_array = rgb_array[top:bottom, left:right]

    if resize is not None:
        rgb_array = cv2.resize(rgb_array, resize)

    if from_space_type == SpaceTypes.GRAY_3ch and to_space_type == SpaceTypes.GRAY_2ch and len(rgb_array.shape) == 3:
        rgb_array = np.squeeze(rgb_array, axis=-1)
    elif len(rgb_array.shape) == 2 and to_space_type == SpaceTypes.GRAY_3ch:
        rgb_array = rgb_array[..., np.newaxis]

    if len(rgb_array.shape) == 3 and shape_order == "CHW":
        rgb_array = np.transpose(rgb_array, (2, 0, 1))

    return rgb_array
