"""Mock assistant actions executed via tool calling."""


def levanta() -> str:
    """Mock action for standing up."""
    print("Mock action executada: levanta()")
    return "Ação levanta executada com sucesso."


def sentar() -> str:
    """Mock action for sitting down."""
    print("Mock action executada: sentar()")
    return "Ação sentar executada com sucesso."


def observar() -> str:
    """Mock action for observing the environment."""
    print("Mock action executada: observar()")
    return "Ação observar executada com sucesso."
