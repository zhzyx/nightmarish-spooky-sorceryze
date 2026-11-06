def can_build(env, platform):
    return True


def configure(env):
    pass


def get_doc_classes():
    return [
        "GameplayComponent",
        "GameplayController",
        "GameplayGameMode",
        "GameplayGameState",
        "GameplayPawn",
        "GameplayPlayerState",
        "GameplaySubsystem",
        "GameplaySubsystemRegistry",
        "GameplayWorld",
        "GameplayConnection",
        "GameplayUserSession",
        "GameplaySessionManager",
        "GameplayServerConfig",
        "GameplayDedicatedServer",
        "GameplaySessionClient",
        "GameplayConnectionView",
        "GameplayRelevancyObject",
        "GameplayReplicationGraph",
        "GameplayPredictionInput",
        "GameplayPredictionState",
        "GameplayPredictionModel",
        "GameplayClientPrediction",
        "GameplayServerPrediction",
        "GameplayInterpolationBuffer",
        "GameplayNetworkSimulator",
        "GameplayNetworkPrediction",
        "GameplayReplicationProperty",
        "GameplayRPCConfig",
        "GameplayReplicationState",
        "GameplayReplicationFragmenter",
        "GameplayMultiplayerReplication",
    ]


def get_doc_path():
    return "doc_classes"
