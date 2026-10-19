"""Bounded alternating MAPPO: independent actors and a shared centralized critic.

Clipped surrogate/GAE follow Schulman et al. (2017), Yu et al. (2022), and
PyTorch's Multi-Agent PPO tutorial. Uses installed torch Adam and Categorical;
no custom optimizer, trajectory replay, or LLM gradient updates.
"""
import copy
import random
import torch
from torch import nn
from .observations import FEATURES
from .io import digest


def network(inputs, outputs):
    return nn.Sequential(nn.Linear(inputs, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh(), nn.Linear(128, outputs))


class Normalizer:
    def __init__(self, size):
        self.n = 0
        self.mean = torch.zeros(size)
        self.m2 = torch.zeros(size)

    def update(self, rows):
        for row in rows:
            x = torch.tensor(row, dtype=torch.float32)
            self.n += 1
            delta = x - self.mean
            self.mean += delta / self.n
            self.m2 += delta * (x - self.mean)

    def apply(self, rows):
        x = torch.as_tensor(rows, dtype=torch.float32)
        if self.n < 2:
            return x
        return ((x - self.mean) / (self.m2 / (self.n - 1)).clamp_min(1e-4).sqrt()).clamp(-10, 10)

    def state_dict(self):
        return dict(n=self.n, mean=self.mean.clone(), m2=self.m2.clone())

    def load_state_dict(self, state):
        self.n, self.mean, self.m2 = state["n"], state["mean"], state["m2"]


def gae(rewards, values, gamma, lam):
    # Complete episode, terminal bootstrap=0; alternating actors share one return.
    adv, last, nxt = [], 0.0, 0.0
    for reward, value in zip(reversed(rewards), reversed(values)):
        last = reward + gamma * nxt - value + gamma * lam * last
        adv.append(last)
        nxt = value
    adv.reverse()
    return adv, [a + v for a, v in zip(adv, values)]


def clipped_actor_loss(new_logp, old_logp, advantage, entropy, clip, entropy_coefficient):
    ratio = (new_logp - old_logp).exp()
    return -torch.minimum(ratio * advantage, ratio.clamp(1 - clip, 1 + clip) * advantage).mean() - entropy_coefficient * entropy.mean()


class MAPPO:
    def __init__(self, config):
        self.config = config
        self.actors = nn.ModuleDict({"evidence": network(FEATURES, 7), "recovery": network(FEATURES, 5)})
        self.critic = network(FEATURES * 2 + 2, 1)
        self.actor_optimizers = {k: torch.optim.Adam(v.parameters(), lr=config["lr"]) for k, v in self.actors.items()}
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=config["lr"])
        self.normalizers = {k: Normalizer(FEATURES) for k in self.actors}

    def centralized(self, views, role):
        return torch.cat([self.normalizers[k].apply(views[k]) for k in ("evidence", "recovery")]
                         + [torch.tensor([float(role == "evidence"), float(role == "recovery")])])

    def choose(self, role, views, mask, deterministic=False):
        obs = self.normalizers[role].apply(views[role])
        central = self.centralized(views, role)
        with torch.no_grad():
            logits = self.actors[role](obs).masked_fill(~torch.tensor(mask, dtype=torch.bool), -1e9)
            distribution = torch.distributions.Categorical(logits=logits)
            action = logits.argmax() if deterministic else distribution.sample()
            logp = distribution.log_prob(action)
            value = self.critic(central).squeeze()
        return int(action), dict(role=role, obs=obs.tolist(), central=central.tolist(), mask=list(mask),
                                 action=int(action), old_logp=float(logp), value=float(value),
                                 raw_views=copy.deepcopy(views))

    @property
    def policy_hash(self):
        return digest({"actors": {k: v.tolist() for k, v in self.actors.state_dict().items()},
                       "normalizers": {k: {n: t.tolist() if torch.is_tensor(t) else t for n, t in v.state_dict().items()}
                                       for k, v in self.normalizers.items()}})

    def update(self, episodes):
        rows = []
        for ep in episodes:
            if not ep["steps"]:
                continue
            values = [r["value"] for r in ep["steps"]]
            rewards = [0.0] * (len(values) - 1) + [ep["reward"]]
            advantages, returns = gae(rewards, values, self.config["gamma"], self.config["gae_lambda"])
            for step, advantage, ret in zip(ep["steps"], advantages, returns):
                rows.append(dict(step, advantage=advantage, ret=ret))
        if not rows:
            raise RuntimeError("no current-policy actor transitions in rollout")
        losses = {}
        for _ in range(self.config["epochs"]):
            # Only the active actor's transitions enter its loss. Old logp and
            # normalized inputs remain fixed through all PPO epochs.
            for role, actor in self.actors.items():
                subset = [r for r in rows if r["role"] == role]
                if not subset:
                    continue
                obs = torch.tensor([r["obs"] for r in subset])
                mask = torch.tensor([r["mask"] for r in subset], dtype=torch.bool)
                dist = torch.distributions.Categorical(logits=actor(obs).masked_fill(~mask, -1e9))
                action = torch.tensor([r["action"] for r in subset])
                adv = torch.tensor([r["advantage"] for r in subset])
                adv = (adv - adv.mean()) / adv.std(unbiased=False).clamp_min(1e-6)
                loss = clipped_actor_loss(dist.log_prob(action), torch.tensor([r["old_logp"] for r in subset]),
                                          adv, dist.entropy(), self.config["clip"], self.config["entropy"])
                optimizer = self.actor_optimizers[role]
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(actor.parameters(), self.config["grad_clip"])
                optimizer.step()
                losses[role] = float(loss.detach())
            central = torch.tensor([r["central"] for r in rows])
            returns = torch.tensor([r["ret"] for r in rows])
            loss = nn.functional.mse_loss(self.critic(central).squeeze(-1), returns)
            self.critic_optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.critic.parameters(), self.config["grad_clip"])
            self.critic_optimizer.step()
            losses["critic"] = float(loss.detach())
        # Normalization freezes within each rollout/update and changes only for
        # the next current-policy rollout. Validation/test never update it.
        for role in self.actors:
            self.normalizers[role].update([r["raw_views"][role] for r in rows])
        return losses

    def state_dict(self):
        return dict(actors=self.actors.state_dict(), critic=self.critic.state_dict(),
                    actor_optimizers={k: v.state_dict() for k, v in self.actor_optimizers.items()},
                    critic_optimizer=self.critic_optimizer.state_dict(),
                    normalizers={k: v.state_dict() for k, v in self.normalizers.items()},
                    torch_rng=torch.get_rng_state(), python_rng=random.getstate())

    def load_state_dict(self, s, restore_rng=True):
        self.actors.load_state_dict(s["actors"])
        self.critic.load_state_dict(s["critic"])
        for k, v in s["normalizers"].items():
            self.normalizers[k].load_state_dict(v)
        for k, v in s["actor_optimizers"].items():
            self.actor_optimizers[k].load_state_dict(v)
        self.critic_optimizer.load_state_dict(s["critic_optimizer"])
        if restore_rng:
            torch.set_rng_state(s["torch_rng"])
            random.setstate(s["python_rng"])
