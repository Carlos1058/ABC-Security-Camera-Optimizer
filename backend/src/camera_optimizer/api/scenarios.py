"""Predefined benchmark scenarios for the ABC Security Camera Optimizer API.

Provides validated, reproducible reference scenarios for demonstration,
benchmarking, and frontend visualization:
1. Empty Warehouse: Clean open space without obstacles, with a central critical area.
2. Partitioned Office: Multi-room facility with interior walls, doorways, columns, and risk zones.
3. Museum Gallery: Complex layout with display pedestals, partitions, and multiple priority artwork zones.
"""

from __future__ import annotations

import math

from camera_optimizer.api.schemas import (
    CameraProfileDTO,
    ObstacleDTO,
    OptimizationConfigDTO,
    PointDTO,
    PredefinedScenarioItemDTO,
    RiskZoneDTO,
    ScenarioDTO,
    WallDTO,
)


def get_empty_warehouse() -> PredefinedScenarioItemDTO:
    """Predefined Scenario 1: Open 20m x 20m facility with no obstacles and a central risk zone."""
    scenario = ScenarioDTO(
        xmin=0.0,
        xmax=20.0,
        ymin=0.0,
        ymax=20.0,
        walls=[],
        obstacles=[],
        risk_zones=[
            RiskZoneDTO(
                vertices=[
                    PointDTO(x=7.0, y=7.0),
                    PointDTO(x=13.0, y=7.0),
                    PointDTO(x=13.0, y=13.0),
                    PointDTO(x=7.0, y=13.0),
                ],
                weight=3.0,
                name="Central Vault Area",
            )
        ],
        grid_resolution=1.0,
    )
    profile = CameraProfileDTO(
        Rmin=0.0,
        Rmax=12.0,
        FOV=math.pi / 2.0,
        p0=1.0,
        beta_d=0.3,
        beta_theta=0.5,
    )
    config = OptimizationConfigDTO(
        K=3,
        SN=15,
        max_cycles=30,
        limit=45,
        seed=42,
        lambda_def=1.0,
        Tcrit=0.8,
        record_population=True,
    )
    return PredefinedScenarioItemDTO(
        id="empty_warehouse",
        name="Empty Warehouse (Open Space)",
        description=(
            "Open 20m x 20m facility without interior obstacles or walls. "
            "Features a 6m x 6m high-priority central vault zone (weight 3.0). Ideal for baseline optimization."
        ),
        scenario=scenario,
        recommended_profile=profile,
        recommended_config=config,
    )


def get_partitioned_office() -> PredefinedScenarioItemDTO:
    """Predefined Scenario 2: 24m x 16m facility with walls, doors, columns, and two risk zones."""
    scenario = ScenarioDTO(
        xmin=0.0,
        xmax=24.0,
        ymin=0.0,
        ymax=16.0,
        # Walls creating a corridor and two rooms with doorway gaps
        walls=[
            # Horizontal dividing wall with a 2m doorway from x=10 to x=12
            WallDTO(start=PointDTO(x=0.0, y=8.0), end=PointDTO(x=10.0, y=8.0), is_opaque=True),
            WallDTO(start=PointDTO(x=12.0, y=8.0), end=PointDTO(x=24.0, y=8.0), is_opaque=True),
            # Vertical wall dividing the top section with a 2m door from y=11 to y=13
            WallDTO(start=PointDTO(x=12.0, y=8.0), end=PointDTO(x=12.0, y=11.0), is_opaque=True),
            WallDTO(start=PointDTO(x=12.0, y=13.0), end=PointDTO(x=12.0, y=16.0), is_opaque=True),
        ],
        # Solid rectangular structural pillar / server rack
        obstacles=[
            ObstacleDTO(
                vertices=[
                    PointDTO(x=4.0, y=3.0),
                    PointDTO(x=7.0, y=3.0),
                    PointDTO(x=7.0, y=5.0),
                    PointDTO(x=4.0, y=5.0),
                ]
            ),
            ObstacleDTO(
                vertices=[
                    PointDTO(x=17.0, y=3.0),
                    PointDTO(x=20.0, y=3.0),
                    PointDTO(x=20.0, y=5.0),
                    PointDTO(x=17.0, y=5.0),
                ]
            ),
        ],
        # Risk zones: Server Room in top-left, Executive Archives in top-right
        risk_zones=[
            RiskZoneDTO(
                vertices=[
                    PointDTO(x=1.0, y=9.0),
                    PointDTO(x=6.0, y=9.0),
                    PointDTO(x=6.0, y=15.0),
                    PointDTO(x=1.0, y=15.0),
                ],
                weight=3.5,
                name="Server Room",
            ),
            RiskZoneDTO(
                vertices=[
                    PointDTO(x=18.0, y=9.0),
                    PointDTO(x=23.0, y=9.0),
                    PointDTO(x=23.0, y=15.0),
                    PointDTO(x=18.0, y=15.0),
                ],
                weight=2.5,
                name="Executive Archives",
            ),
        ],
        grid_resolution=0.8,
    )
    profile = CameraProfileDTO(
        Rmin=0.2,
        Rmax=11.0,
        FOV=math.pi / 2.0,
        p0=1.0,
        beta_d=0.4,
        beta_theta=0.5,
    )
    config = OptimizationConfigDTO(
        K=4,
        SN=20,
        max_cycles=40,
        limit=60,
        seed=100,
        lambda_def=1.5,
        Tcrit=0.8,
        record_population=True,
    )
    return PredefinedScenarioItemDTO(
        id="partitioned_office",
        name="Partitioned Office with Corridors & Doors",
        description=(
            "24m x 16m multi-room facility with interior partitions, 2m doorway passages, "
            "two solid structural columns, and two high-priority risk zones (Server Room and Executive Archives)."
        ),
        scenario=scenario,
        recommended_profile=profile,
        recommended_config=config,
    )


def get_museum_gallery() -> PredefinedScenarioItemDTO:
    """Predefined Scenario 3: 30m x 20m museum exhibition space with display barriers."""
    scenario = ScenarioDTO(
        xmin=0.0,
        xmax=30.0,
        ymin=0.0,
        ymax=20.0,
        walls=[
            # Central dividing partition with wide passages on both sides
            WallDTO(start=PointDTO(x=8.0, y=10.0), end=PointDTO(x=22.0, y=10.0), is_opaque=True),
        ],
        obstacles=[
            # Central sculpture pedestals
            ObstacleDTO(
                vertices=[
                    PointDTO(x=5.0, y=4.0),
                    PointDTO(x=8.0, y=4.0),
                    PointDTO(x=8.0, y=6.0),
                    PointDTO(x=5.0, y=6.0),
                ]
            ),
            ObstacleDTO(
                vertices=[
                    PointDTO(x=22.0, y=4.0),
                    PointDTO(x=25.0, y=4.0),
                    PointDTO(x=25.0, y=6.0),
                    PointDTO(x=22.0, y=6.0),
                ]
            ),
            ObstacleDTO(
                vertices=[
                    PointDTO(x=13.0, y=14.0),
                    PointDTO(x=17.0, y=14.0),
                    PointDTO(x=17.0, y=17.0),
                    PointDTO(x=13.0, y=17.0),
                ]
            ),
        ],
        risk_zones=[
            RiskZoneDTO(
                vertices=[
                    PointDTO(x=2.0, y=2.0),
                    PointDTO(x=11.0, y=2.0),
                    PointDTO(x=11.0, y=8.0),
                    PointDTO(x=2.0, y=8.0),
                ],
                weight=4.0,
                name="Masterpiece Gallery Wing",
            ),
            RiskZoneDTO(
                vertices=[
                    PointDTO(x=11.0, y=12.0),
                    PointDTO(x=19.0, y=12.0),
                    PointDTO(x=19.0, y=19.0),
                    PointDTO(x=11.0, y=19.0),
                ],
                weight=3.0,
                name="Ancient Artifacts Wing",
            ),
        ],
        grid_resolution=1.0,
    )
    profile = CameraProfileDTO(
        Rmin=0.0,
        Rmax=14.0,
        FOV=math.pi / 2.0,
        p0=1.0,
        beta_d=0.3,
        beta_theta=0.5,
    )
    config = OptimizationConfigDTO(
        K=5,
        SN=25,
        max_cycles=50,
        limit=75,
        seed=777,
        lambda_def=2.0,
        Tcrit=0.85,
        record_population=True,
    )
    return PredefinedScenarioItemDTO(
        id="museum_gallery",
        name="Museum Exhibition Gallery",
        description=(
            "30m x 20m exhibition hall featuring multiple display pedestals, partition walls, "
            "and two high-value artwork wings requiring rigorous surveillance."
        ),
        scenario=scenario,
        recommended_profile=profile,
        recommended_config=config,
    )


ALL_PREDEFINED_SCENARIOS: list[PredefinedScenarioItemDTO] = [
    get_empty_warehouse(),
    get_partitioned_office(),
    get_museum_gallery(),
]
