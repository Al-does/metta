from omegaconf import OmegaConf
import os
import torch
import warnings
import wandb
import random
def load_policy_from_file(path: str, device: str):
    assert path.endswith('.pt'), f"Policy file {path} does not have a .pt extension"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        policy = torch.load(path, map_location=device, weights_only=False)
        policy.path = path
    return policy

def load_policy_from_wandb(uri: str, cfg: OmegaConf, wandb_run):
    artifact_path = uri[len("wandb://"):]
    if "@" in artifact_path:
        path, selector = artifact_path.split("@")
        atype, name = path.split("/")
        collection = wandb.Api().artifact_collection(
            type_name=atype,
            name=f"{cfg.wandb.entity}/{cfg.wandb.project}/{name}")
        artifact = select_artifact(collection, selector)
    else:
        artifact = wandb_run.use_artifact(uri[len("wandb://"):])
    data_dir = artifact.download(root=os.path.join(cfg.data_dir, "artifacts"))
    print(f"Downloaded artifact {artifact.name} to {data_dir}")
    return load_policy_from_file(
        os.path.join(data_dir, "model.pt"),
        cfg.device
    )


def load_policy_from_dir(path: str, device: str):
    trainer_state = torch.load(os.path.join(path, 'trainer_state.pt'))
    model_path = os.path.join(path, trainer_state["model_name"])
    return load_policy_from_file(model_path, device)

def load_policy_from_uri(uri: str, cfg: OmegaConf, wandb_run):
    print(f"Loading policy from {uri}")
    policy = None
    if uri.startswith("wandb://"):
        policy = load_policy_from_wandb(uri, cfg, wandb_run)
    elif uri.endswith(".pt"):
        policy = load_policy_from_file(uri, cfg.device)
    else:
        policy = load_policy_from_dir(uri, cfg.device)
    print(f"Loaded policy from {uri}")
    policy.uri = uri
    return policy

def load_policies_from_dir(path: str, cfg: OmegaConf):
    print(f"Loading policies from {path}")
    policies = []
    for file in os.listdir(path):
        if file.endswith(".pt") and file.startswith("model_"):
            policies.append(load_policy_from_file(os.path.join(path, file), cfg.device))
    print(f"Loaded {len(policies)} policies")
    return policies

def load_policies_from_wandb(uri: str, cfg: OmegaConf, wandb_run):
    artifact = wandb_run.use_artifact(uri[len("wandb://"):], type="model")
    return load_policies_from_dir(artifact.download(
        root=os.path.join(cfg.data_dir, "artifacts")
    ), cfg)

def count_params(policy):
    return sum(p.numel() for p in policy.parameters() if p.requires_grad)

def upload_policy_to_wandb(
        wandb_run,
        policy_path,
        name,
        metadata=None, artifact_type="model",
        additional_files=None,
    ):

    artifact = wandb.Artifact(
        name,
        type=artifact_type,
        metadata=metadata or {}
    )
    artifact.add_file(policy_path, name="model.pt")
    if additional_files:
        for file in additional_files:
            artifact.add_file(file)
    artifact.save()
    artifact.wait()
    wandb_run.log_artifact(artifact)
    print(f"Uploaded model to wandb: {artifact.name} to run {wandb_run.id}")
    return artifact

def select_artifact(collection, selector: str):
    artifacts = list(collection.artifacts())
    if selector == "rand":
        return random.choice(artifacts)
    elif selector == "best":
        a = max(artifacts, key=lambda x: x.metadata.get("eval_metric", 0))
        print(f"Selected artifact {a.name} with eval_metric {a.metadata.get('eval_metric', 0)}")
        return a
    elif selector.startswith("best."):
        _, metric = selector.split(".")
        a = max(artifacts, key=lambda x: x.metadata.get(metric, 0))
        print(f"Selected artifact {a.name} with eval_metric {a.metadata.get(metric, 0)}")
        return a
    elif selector.startswith("top_"):
        n, metric = selector[len("top_"):].split(".")
        n = int(n)
        top = sorted(artifacts, key=lambda x: x.metadata.get(metric, 0))[-n:]
        print(f"Top {n} artifacts by {metric}:")
        print(f"{'Artifact':<40} | {metric:<20}")
        print("-" * 62)
        for a in top:
            print(f"{a.name:<40} | {a.metadata.get(metric, 0):<20.4f}")
        return random.choice(top)
    else:
        raise ValueError(f"Invalid selector {selector}")
