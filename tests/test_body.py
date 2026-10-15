import numpy as np

from flybrain.body import FlyBody
from flybrain.scene import FlyStart


def test_walks_forward_along_heading():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=90), seed=0)
    s0 = b.state()
    s1 = b.step(np.array([1.0, 1.0]), 1000)
    disp = s1.thorax[:2] - s0.thorax[:2]
    assert np.dot(disp, [0, 1]) > 0.3 and abs(disp[0]) < np.dot(disp, [0, 1])
    assert np.allclose(s0.forward[:2], [0, 1], atol=0.1)


def test_smaller_left_drive_turns_left():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    b.step(np.array([1.0, 1.0]), 300)
    s = b.step(np.array([0.3, 1.2]), 1000)
    assert s.forward[1] > 0.05  # yawed toward +y (left)


def test_part_poses_shape_and_unit_quaternions():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    p = b.part_poses()
    assert p.shape == (69, 7) and p.dtype == np.float32 and len(b.part_names) == 69
    assert np.allclose(np.linalg.norm(p[:, 3:], axis=1), 1, atol=1e-4)
    assert b.state().finite and not b.state().flipped


def test_spawn_position_respected():
    b = FlyBody(FlyStart(pos=(5, -3), heading_deg=0), seed=0)
    assert np.allclose(b.state().thorax[:2], [5, -3], atol=0.5)


def test_eye_positions_are_separated():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    s = b.state()
    assert s.eye_left[1] - s.eye_right[1] > 0.4  # left eye on +y at heading 0
    assert s.head[0] > s.thorax[0]


def test_physics_blowup_returns_non_finite_instead_of_raising():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    b.step(np.array([1.0, 1.0]), 10)
    b.sim.physics.data.qvel[:] = 1e30
    s = b.step(np.array([1.0, 1.0]), 50)
    assert not s.finite
