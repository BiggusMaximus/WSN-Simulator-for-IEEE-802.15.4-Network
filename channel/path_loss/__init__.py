from abstract.path_loss import PathLossModel
from .basic import LogDistance
from .ITU import ITU_P1411
from .ideal import Ideal
from .SUI import SUI_TypeA, SUI_TypeB, SUI_TypeC
from .Ericsson import EricssonUrban
from utils.information import console

PATH_LOSS_REGISTRY = {
    'LogDistance' : LogDistance,
    'ITU_P1411'   : ITU_P1411,
    'Ideal'       : Ideal,
    'SUI_TypeA'   : SUI_TypeA,
    'SUI_TypeB'   : SUI_TypeB,
    'SUI_TypeC'   : SUI_TypeC,
    'EricssonUrban': EricssonUrban,
}

def create_path_loss(config) -> PathLossModel:
    path_loss_name = config['name']
    if path_loss_name not in PATH_LOSS_REGISTRY:
        console.print(
            f"[bold red]Unknown path_loss model: {path_loss_name}. "
            f"Available: {list(PATH_LOSS_REGISTRY.keys())}[/bold red]"
        )
    return PATH_LOSS_REGISTRY[path_loss_name](config)
