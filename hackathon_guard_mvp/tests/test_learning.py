"""CPU mathematical unit checks only; no campaign or language model execution."""
import copy
import unittest
import torch
from guard_mvp.learner import MAPPO, Normalizer, gae, clipped_actor_loss
from guard_mvp.train import choose_case


CONFIG = dict(lr=3e-4, gamma=.99, gae_lambda=.95, epochs=4, clip=.2, entropy=.01, grad_clip=.5)


class Learning(unittest.TestCase):
    def test_gae_terminal_and_episode_boundaries(self):
        adv, ret = gae([0, 10], [1, 2], 1, 1)
        self.assertEqual(adv, [9, 8])
        self.assertEqual(ret, [10, 10])
        self.assertEqual(gae([0], [2], 1, 1), ([-2.0], [0.0]))

    def test_clipping_and_valid_actor_gradient(self):
        logp = torch.tensor([0.0, 0.0], requires_grad=True)
        old = torch.tensor([0.0, 0.0])
        loss = clipped_actor_loss(logp, old, torch.tensor([1.0, -1.0]), torch.zeros(2), .2, 0)
        loss.backward()
        self.assertTrue(torch.allclose(logp.grad, torch.tensor([-.5, .5])))

    def test_actors_have_disjoint_parameters_and_active_gradients(self):
        p = MAPPO(CONFIG)
        first = {id(x) for x in p.actors["evidence"].parameters()}
        self.assertFalse(first.intersection(id(x) for x in p.actors["recovery"].parameters()))
        views = {"evidence": [0.] * 16, "recovery": [0.] * 16}
        action, row = p.choose("evidence", views, [True] * 7)
        self.assertEqual(row["role"], "evidence")
        self.assertEqual(len(row["central"]), 34)
        logits = p.actors["evidence"](torch.tensor(row["obs"]))
        torch.distributions.Categorical(logits=logits).log_prob(torch.tensor(action)).backward()
        self.assertTrue(all(v.grad is None for v in p.actors["recovery"].parameters()))
        self.assertTrue(all(v.grad is None for v in p.critic.parameters()))

    def test_normalization_persists_and_validation_does_not_update(self):
        p = MAPPO(CONFIG)
        for n in p.normalizers.values():
            n.update([[1.] * 16, [3.] * 16])
        q = MAPPO(CONFIG)
        q.load_state_dict(copy.deepcopy(p.state_dict()))
        self.assertEqual(q.policy_hash, p.policy_hash)
        before = q.policy_hash
        for _ in range(3):
            q.choose("recovery", {"evidence": [2.] * 16, "recovery": [2.] * 16}, [True] * 5, True)
        self.assertEqual(q.policy_hash, before)
        self.assertEqual(q.normalizers["recovery"].n, 2)

    def test_rng_resume_idempotency(self):
        p = MAPPO(CONFIG)
        views = {"evidence": [0.] * 16, "recovery": [0.] * 16}
        saved = copy.deepcopy(p.state_dict())
        actions = [p.choose("evidence", views, [True] * 7)[0] for _ in range(6)]
        q = MAPPO(CONFIG)
        q.load_state_dict(saved)
        self.assertEqual(actions, [q.choose("evidence", views, [True] * 7)[0] for _ in range(6)])

    def test_availability_mask_is_respected(self):
        p = MAPPO(CONFIG)
        views = {"evidence": [0.] * 16, "recovery": [0.] * 16}
        self.assertEqual(p.choose("evidence", views, [False] * 6 + [True])[0], 6)

    def test_rollout_sampling_balances_clean_surfaces_and_workflows(self):
        from collections import Counter
        rows = [dict(workflow=w, surface=s) for w in ("receipt", "supplier", "collection") for s in ("clean", "document", "handoff")]
        chosen = [choose_case(rows, i, 17) for i in range(120)]
        self.assertEqual(Counter(r["surface"] for r in chosen), {"clean": 60, "document": 30, "handoff": 30})
        self.assertEqual(Counter(r["workflow"] for r in chosen), {"receipt": 40, "supplier": 40, "collection": 40})


if __name__ == "__main__":
    unittest.main()
