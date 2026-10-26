# ABC Security Camera Optimizer — Backend

Núcleo computacional y API REST del proyecto de optimización de cámaras de seguridad mediante el algoritmo Artificial Bee Colony (ABC) estrictamente secuencial.

---

## 1. Requisitos del Entorno

- **Python:** 3.11 o superior (probado y validado en Python 3.14).
- **Dependencias principales:**
  - `numpy>=2.0.0`
  - `pydantic>=2.0.0`
  - `fastapi>=0.100.0`
  - `uvicorn>=0.20.0`
- **Dependencias de prueba y desarrollo:**
  - `pytest>=8.0.0`
  - `httpx>=0.25.0`

> **Regla de integridad:** El algoritmo de optimización ABC es **estrictamente secuencial**. No utiliza multiprocessing, multithreading, OpenMP ni GPU para el núcleo de optimización.

---

## 2. Estructura del Proyecto

```
backend/
├── pyproject.toml
├── README.md
├── tests/
│   ├── test_geometry.py             # 25 pruebas: primitivas geométricas, segmentos, polígonos
│   ├── test_floorplan.py            # 18 pruebas: recintos, paredes, obstáculos, visibilidad
│   ├── test_sampling_grid.py        # 12 pruebas: generación de mallas y exportación
│   ├── test_camera.py               # 13 pruebas: modelos ópticos y poses de cámaras
│   ├── test_coverage.py             # 11 pruebas: cobertura probabilística y visibilidad
│   ├── test_objective.py            # 8 pruebas: evaluador de configuración y función objetivo
│   ├── test_camera_optimization.py  # 6 pruebas: integración del problema de cámaras con ABC
│   ├── test_abc_engine.py           # 28 pruebas: motor secuencial ABC, telemetría y casos límite (SN=2, limit=1)
│   └── test_api.py                  # 19 pruebas: endpoints FastAPI, validación, determinismo y concurrencia
└── src/
    └── camera_optimizer/
        ├── __init__.py
        ├── main.py                  # Punto de entrada para servidor Uvicorn
        ├── geometry/                # Fase 1: Núcleo geométrico 2D
        │   ├── point.py
        │   ├── bounding_box.py
        │   ├── segment.py
        │   ├── intersections.py
        │   └── polygon.py
        ├── domain/                  # Fase 1: Dominio espacial
        │   ├── wall.py
        │   ├── obstacle.py
        │   ├── risk_zone.py
        │   ├── floorplan.py
        │   └── grid.py
        ├── camera/                  # Fase 2: Modelo óptico de cámaras
        │   ├── pose.py
        │   └── profile.py
        ├── coverage/                # Fase 2: Cobertura multi-cámara
        │   ├── metrics.py
        │   └── evaluator.py
        ├── objective/               # Fase 2: Función objetivo de minimización
        │   ├── config.py
        │   └── evaluator.py
        ├── optimizer/               # Fase 3: Motor Sequential ABC
        │   ├── bounds.py
        │   ├── config.py
        │   ├── food_source.py
        │   ├── problem.py
        │   ├── camera_problem.py
        │   ├── sequential_abc.py
        │   └── tracking.py
        └── api/                     # Fase 4: Backend FastAPI y DTOs
            ├── __init__.py
            ├── limits.py            # Límites de recursos y justificaciones
            ├── schemas.py           # Contratos de datos tipados (Pydantic DTOs)
            ├── scenarios.py         # Escenarios de demostración predefinidos
            ├── service.py           # Capa de servicio y bloqueo de concurrencia
            ├── router.py            # Rutas y controladores HTTP REST
            └── app.py               # Fábrica de la aplicación FastAPI con CORS
```

---

## 3. Endpoints de la API REST

Base URL: `http://localhost:8000/api/v1`

### 3.1. `GET /api/v1/health`
Verifica el estado del servicio, versión y si hay una optimización en curso.
- **Respuesta 200 OK:**
  ```json
  {
    "status": "ok",
    "service": "ABC Security Camera Optimizer API",
    "version": "0.4.0",
    "is_busy": false,
    "details": {
      "is_busy": false,
      "active_run_id": null,
      "elapsed_seconds": null
    }
  }
  ```

### 3.2. `GET /api/v1/scenarios`
Devuelve el catálogo de escenarios de demostración predefinidos y reproducibles:
- `empty_warehouse`: Recinto diáfano de 20m × 20m sin obstáculos ni paredes interiores, con zona de riesgo central (bóveda, peso 3.0).
- `partitioned_office`: Instalación de 24m × 16m con tabiques divisorios, puertas de paso de 2m, columnas estructurales y dos zonas de riesgo (Sala de Servidores y Archivo).
- `museum_gallery`: Sala de exhibición de 30m × 20m con pedestales de esculturas, particiones y dos alas de arte prioritario.

### 3.3. `POST /api/v1/scenarios/validate`
Valida la geometría, el perfil óptico y los hiperparámetros antes de ejecutar ABC.
- **Entrada:** `ValidationRequest` (scenario, profile, config).
- **Respuesta 200 OK:**
  ```json
  {
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "details": {
      "estimated_grid_cells": 600,
      "actual_grid_nodes": 584
    }
  }
  ```
  Si hay errores topológicos o geométricos (polígonos autointersecantes, paredes fuera de recinto, resolución desproporcionada), devuelve `is_valid: false` y la lista de mensajes explicativos.

### 3.4. `POST /api/v1/optimize/run`
Ejecuta de forma real y secuencial el algoritmo ABC sobre el escenario configurado y devuelve los resultados completos.
- **Bloqueo de concurrencia:** Si existe una ejecución en curso, devuelve inmediatamente `409 Conflict` (`"Another optimization run is currently executing. The ABC engine is strictly sequential..."`).
- **Respuesta 200 OK:** `OptimizationResultDTO` con:
  - Dimensionalidad exacta $3K$.
  - Mejor configuración inicial (ciclo 0) y final ($K$ poses con $x, y, \theta$ en radianes y grados).
  - Trayectoria de costos `best_cost_per_cycle` y `mean_cost_per_cycle`.
  - Métricas completas de cobertura (`geometric_coverage_percent`, `risk_weighted_coverage`, `critical_deficit`).
  - Métricas de esfuerzo (`total_evaluations` / NFE, `total_proposals`, `rejected_infeasible_proposals`, `total_scout_resets`, `execution_time_seconds`).
  - Historial poblacional opcional por ciclo para reproducción visual interactiva en el frontend.

### 3.5. Ejemplo Real y Reproducible de Solicitud y Respuesta (Auditoría Verificada)

A continuación se presenta la ejecución real obtenida mediante `TestClient` con semilla 42, exactamente contrastada en auditoría:

#### Solicitud HTTP:
`POST /api/v1/optimize/run`
```json
{
  "scenario": {
    "xmin": 0.0,
    "xmax": 24.0,
    "ymin": 0.0,
    "ymax": 16.0,
    "walls": [
      { "start": { "x": 0.0, "y": 8.0 }, "end": { "x": 10.0, "y": 8.0 }, "is_opaque": true },
      { "start": { "x": 12.0, "y": 8.0 }, "end": { "x": 24.0, "y": 8.0 }, "is_opaque": true }
    ],
    "obstacles": [
      {
        "vertices": [
          { "x": 4.0, "y": 3.0 }, { "x": 7.0, "y": 3.0 },
          { "x": 7.0, "y": 5.0 }, { "x": 4.0, "y": 5.0 }
        ]
      }
    ],
    "risk_zones": [
      {
        "vertices": [
          { "x": 1.0, "y": 9.0 }, { "x": 6.0, "y": 9.0 },
          { "x": 6.0, "y": 15.0 }, { "x": 1.0, "y": 15.0 }
        ],
        "weight": 3.5,
        "name": "Server Room"
      }
    ],
    "grid_resolution": 1.0
  },
  "profile": {
    "Rmin": 0.2,
    "Rmax": 11.0,
    "FOV": 1.5707963,
    "p0": 1.0,
    "beta_d": 0.4,
    "beta_theta": 0.5
  },
  "config": {
    "K": 3,
    "SN": 10,
    "max_cycles": 15,
    "limit": 45,
    "seed": 42,
    "lambda_def": 1.0,
    "Tcrit": 0.8,
    "record_population": true
  }
}
```

#### Respuesta HTTP (`200 OK` real obtenida):
```json
{
  "scenario": { ... },
  "profile": { "Rmin": 0.2, "Rmax": 11.0, "FOV": 1.5707963, "p0": 1.0, "beta_d": 0.4, "beta_theta": 0.5 },
  "config": { "K": 3, "SN": 10, "max_cycles": 15, "limit": 45, "seed": 42, "lambda_def": 1.0, "Tcrit": 0.8, "record_population": true },
  "effective_seed": 42,
  "dimension": 9,
  "initial_best_cost": 1.4690508302716077,
  "initial_best_poses": [
    { "x": 19.314, "y": 6.200, "theta": -1.330, "theta_deg": -76.20 },
    { "x": 16.380, "y": 2.236, "theta": -1.886, "theta_deg": -108.03 },
    { "x": 0.177,  "y": 12.591, "theta": 1.036,  "theta_deg": 59.35 }
  ],
  "final_best_cost": 0.7012359027263447,
  "final_best_poses": [
    { "x": 19.314, "y": 7.652, "theta": -1.330, "theta_deg": -76.20 },
    { "x": 16.033, "y": 7.141, "theta": -2.660, "theta_deg": -152.42 },
    { "x": 0.177,  "y": 12.591, "theta": -0.243, "theta_deg": -13.92 }
  ],
  "best_cost_per_cycle": [
    1.4690508302716077, 1.4379553706446528, 1.4379553706446528, 0.828758846026136,
    0.828758846026136, 0.7969307382781511, 0.7736858951045499, 0.7736858951045499,
    0.7728915908381476, 0.7566686165129783, 0.7566686165129783, 0.7566686165129783,
    0.7565230084048526, 0.71130138491591, 0.7065135200506959, 0.7012359027263447
  ],
  "coverage_metrics": {
    "num_eval_points": 378,
    "num_covered_points": 188,
    "geometric_coverage_ratio": 0.4973544973544973,
    "geometric_coverage_percent": 49.735449735449734,
    "mean_probabilistic_coverage": 0.38197180503724154,
    "risk_weighted_coverage": 0.43686903876964234,
    "num_critical_points": 30,
    "critical_deficit": 0.13810494149598704
  },
  "total_evaluations": 287,
  "total_proposals": 310,
  "rejected_infeasible_proposals": 23,
  "total_scout_resets": 0,
  "execution_time_seconds": 0.763,
  "population_history_available": true
}
```

#### Verificación Matemática Interna:
$$f(X) = (1 - C_{risk}) + \lambda_{def} \times \text{Deficit}_{crit}$$
$$(1 - 0.43686903876964234) + 1.0 \times 0.13810494149598704 = 0.5631309612303577 + 0.13810494149598704 = 0.7012359027263447$$
La identidad matemática coincide de forma exacta con error absoluto nulo ($\Delta = 0.00 \times 10^{-16}$).

---

## 4. Ejecución del Servidor Local

Para iniciar el servidor FastAPI localmente:

```bash
# Opción A: Usando Uvicorn directamente
cd backend
uvicorn camera_optimizer.main:app --host 127.0.0.1 --port 8000 --reload

# Opción B: Mediante el módulo principal
cd backend
python3 -m camera_optimizer.main
```

Documentación interactiva disponible en:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 5. Ejecución de Pruebas Automatizadas

Para ejecutar la suite completa de 149 pruebas (121 del núcleo computacional + 28 de API y verificación de defectos):

```bash
cd backend
python3 -m pytest -v
```

Para ejecutar pruebas específicas de la API:

```bash
python3 -m pytest tests/test_api.py -v
```

---

## 6. Ajustes Algorítmicos Documentados (Auditoría Especializada)

1. **Selección Greedy Estricta:**
   La selección greedy implementada en las abejas empleadas y observadoras exige mejora estricta del costo ($f(v) < f(x)$), lo que equivale a mayor aptitud ($\text{fitness}(v) > \text{fitness}(x)$). Esta regla reproduce fielmente la implementación canónica de referencia en MATLAB v2 de D. Karaboga & B. Akay (`if (FitnessSol > Fitness(i))`), descargable en [https://abc.erciyes.edu.tr/form.aspx](https://abc.erciyes.edu.tr/form.aspx).
2. **Política de Infactibilidad:**
   Toda propuesta vecina que viole las restricciones espaciales del recinto (cámara dentro de un obstáculo, sobre una pared o fuera de la sala) es rechazada antes de la evaluación de la función objetivo e incrementa explícitamente el contador `trial` de la fuente de alimento. Esto previene estancamiento en regiones infactibles.
3. **Probabilidades de Observadoras Fijas:**
   Las probabilidades de selección por ruleta se calculan a partir de la aptitud de la población al inicio de la fase de observadoras y permanecen constantes durante los $SN$ intentos de selección de ese ciclo.
4. **Criterio de Abandono Scout:**
   El criterio adoptado es $\text{trial} \ge \text{limit}$. En cada ciclo se evalúa la fuente con mayor contador `trial`, y si alcanza o supera el límite, es abandonada y reinicializada por una abeja exploradora (a lo sumo 1 sustitución por ciclo).
5. **Prueba de Límite (SN=2, limit=1):**
   Verificada mediante `test_abc_sn2_limit1_execution_and_accounting()`, demostrando ausencia de bucles infinitos, terminación secuencial limpia y contabilidad exacta de NFE.

---

## 7. Presupuesto Computacional y Gestión de Recursos (Fase 4.1)

Para prevenir denegación de servicio por combinaciones desproporcionadas de parámetros manteniendo amplia admisibilidad de escenarios académicos, la API aplica cotas teóricas conservadoras evaluadas **antes** de instanciar el algoritmo:

1. **Cota Superior de Evaluaciones de Función Objetivo:**
   $$NFE_{upper} = SN + 2 \times SN \times \text{MaxCycles} + \text{MaxCycles}$$
2. **Cota Superior de Carga de Trabajo Global:**
   $$work_{upper} \approx NFE_{upper} \times K \times N_{grid} \le 100\,000\,000 \text{ ops}$$
   - Un escenario académico típico ($K=4$, $SN=20$, $\text{MaxCycles}=40$, $N=600$) consume $\approx 4 \times 10^6$ ops ($4\%$ del presupuesto).
   - Combinaciones astronómicas (ej. $K=30$, $SN=100$, $\text{MaxCycles}=1000$, $N=50\,000 \implies 3 \times 10^{11}$ ops) son rechazadas tempranamente con mensaje explicativo.
3. **Límite de Historial Poblacional:**
   $$\text{elements} = (\text{MaxCycles} + 1) \times SN \times K \le 50\,000$$
   Asegura que el historial para reproducción visual en Canvas/React no supere $\approx 5\text{ MB}$ de carga JSON en memoria o red.

---

## 8. Reproducibilidad y Semilla Efectiva

- **Semilla explícita:** Si el cliente suministra un entero $seed \ge 0$, se utiliza exactamente sin alteración.
- **Semilla omitida (`null`):** La API genera un entero criptográficamente seguro de 63 bits mediante `secrets.randbits(63)`. Este valor concreto se transfiere al motor ABC y se reporta en `effective_seed`.
- **Reproducción determinista garantizada:** Repetir una solicitud utilizando el `effective_seed` devuelto reproduce con exactitud bit a bit la trayectoria de costos, mejores poses y conteos de propuestas, excluyendo únicamente el tiempo de reloj (`execution_time_seconds`).

