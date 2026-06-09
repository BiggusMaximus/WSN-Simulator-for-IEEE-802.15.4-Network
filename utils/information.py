from rich.table import Table
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule 

console = Console(record=True)


def _build_config_table(title: str, config_section: dict) -> Table:
    """Return a centred Rich Table summarising a config section."""
    table = Table(
        title=title, 
        show_header=True,
        header_style="bold cyan", 
        pad_edge=False
    )
    table.add_column("Parameter", style="bold")
    table.add_column("Value")

    for key, value in config_section.items():
        if isinstance(value, dict):
            # The first level key is a component name; use the value
            # that matches the section's own "name" field (e.g. config_section["name"])
            section_name = config_section.get("name")
            sub_dict = value.get(section_name) if section_name else value
            if sub_dict:
                sub = Table(show_header=False, box=None, pad_edge=False)
                sub.add_column("Sub-Parameter", style="dim")
                sub.add_column("Value")
                for k, v in sub_dict.items():
                    sub.add_row(k, str(v))
                table.add_row(key, sub)
        else:
            table.add_row(key, str(value))

    return Align.center(table, vertical="middle")


def simulation_summaries(config):
    console.print()  # blank line (use console.print instead of print)

    version = config['Simulation']["version"]
    console.print(f"# WSN Simulation (v{version}) - A. B. Dewantara\n")
    console.print()

    # Define which sections to print and their titles
    sections = [
        ("Node Sensor Summary", "Sensor"),       # first special case
        ("WSN Environment Summary", "Simulation"),
        ("Node Summary", "Node"),
        ("MCU Summary", "MCU"),
        ("RF Summary", "RF"),
        ("Channel Summary", "Channel"),
        ("Routing Summary", "Routing"),
    ]

    for title, cfg_key in sections:
        console.print(_build_config_table(title, config[cfg_key]))
        console.print()   # blank line separator
