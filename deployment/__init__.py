from abstract.deployment import Deployment
from .random import Random
from .poisson import PoissonLineCox
from .user import UserInput
from utils.information import console

DEPLOYMENT_REGISTRY  = {
    'Random': Random,
    'PoissonLineCox': PoissonLineCox,
    'UserInput': UserInput,
}

def create_deployment(config) -> Deployment:
    deployment_name = config["Deployment"]["name"]

    if deployment_name not in DEPLOYMENT_REGISTRY:
        console.print(f"[bold red]Unknown deployment strategy: {deployment_name}. Available: {DEPLOYMENT_REGISTRY.keys()}[/bold red]")

    return DEPLOYMENT_REGISTRY[deployment_name](config)
