# ABC Security Camera Optimizer

**Optimización de la ubicación y orientación de cámaras de seguridad mediante el algoritmo Artificial Bee Colony (ABC)**

## Información académica

**Institución:** Universidad Autónoma de Aguascalientes (UAA)  
**Programa educativo:** Ingeniería en Computación Inteligente  
**Asignatura:** Paralelización de Algoritmos  
**Tipo de proyecto:** Desarrollo e implementación de un algoritmo de optimización secuencial  
**Fecha:** Octubre de 2026

### Integrantes del equipo

- **Carlos Abraham Negrete de la Cruz**
- **Evelyn Vanessa Campos Aguayo**
- **Yaretzi Castillo Morales**

---

## 1. Descripción del proyecto

**ABC Security Camera Optimizer** es una aplicación interactiva que busca mejorar la distribución de cámaras de seguridad dentro de un recinto bidimensional. Permite diseñar escenarios arquitectónicos, definir zonas que requieren mayor vigilancia y ejecutar un algoritmo de optimización para proponer posiciones y orientaciones de cámaras.

El sistema integra un editor visual de planos, una simulación geométrica y probabilística de cobertura y un motor de optimización basado en **Artificial Bee Colony (ABC)**. Los resultados se visualizan sobre el plano mediante cámaras, campos de visión y mapas de cobertura, junto con métricas y una curva de convergencia.

## 2. Problema que se busca resolver

Colocar cámaras de seguridad de manera intuitiva no garantiza una cobertura eficiente: pueden existir puntos ciegos, obstáculos que bloquean la visión, cámaras orientadas hacia áreas poco útiles o zonas de alta prioridad insuficientemente vigiladas.

El problema consiste en **determinar la posición y orientación de un número fijo de cámaras** para mejorar la cobertura de un espacio, considerando:

- Dimensiones del recinto, paredes, puertas y obstáculos.
- Alcance máximo y campo de visión de cada cámara.
- Probabilidad simulada de detección en cada punto.
- Zonas de riesgo con diferentes pesos de importancia.
- Restricciones físicas de ubicación de las cámaras.

El objetivo es minimizar una función de costo que considera la cobertura ponderada por riesgo y el déficit de detección en zonas críticas.

## 3. Algoritmo utilizado: Artificial Bee Colony (ABC)

El **Artificial Bee Colony (ABC)** es una metaheurística inspirada en el comportamiento de búsqueda de alimento de las abejas. Cada *fuente de alimento* representa una solución candidata; en este proyecto, una solución corresponde a las posiciones y orientaciones de todas las cámaras.

Para **K cámaras**, cada solución se representa con un vector de **3K variables**:

`X = [x1, y1, θ1, x2, y2, θ2, ..., xK, yK, θK]`

El algoritmo trabaja en tres etapas principales:

1. **Abejas empleadas (Employed Bees):** exploran nuevas configuraciones cercanas a las soluciones actuales.
2. **Abejas observadoras (Onlooker Bees):** seleccionan soluciones según su aptitud y buscan mejoras adicionales.
3. **Abejas exploradoras (Scout Bees):** reemplazan soluciones estancadas por nuevas configuraciones, favoreciendo la exploración.

Durante la ejecución, el sistema registra la mejor solución encontrada y permite observar su evolución por ciclos.

> **Importante:** En esta entrega, el algoritmo ABC es **estrictamente secuencial**. No se paralelizan las fases ni las evaluaciones de las soluciones.

### Función objetivo

La optimización minimiza:

`f(X) = (1 - C_risk) + λ × Deficit_crit`

Donde:

- `C_risk` es la cobertura probabilística ponderada según la importancia de cada zona.
- `Deficit_crit` mide cuánto falta para alcanzar el umbral de detección deseado en las zonas críticas.
- `λ` controla la importancia de penalizar dicho déficit.

**Un costo menor representa una solución mejor según este modelo.** Las probabilidades provienen de una simulación matemática, no de mediciones experimentales de cámaras comerciales.

## 4. Funcionalidades principales

- Creación de planos 2D desde cero o a partir de escenarios predefinidos.
- Edición visual de paredes, aberturas, obstáculos y zonas de riesgo.
- Importación y exportación de escenarios en formato JSON.
- Configuración del número de cámaras y de parámetros avanzados del algoritmo.
- Optimización automática de ubicación y orientación mediante ABC secuencial.
- Visualización del campo de visión nominal y de la cobertura geométrica.
- Mapas de calor de probabilidad de detección calculados por el backend.
- Visualización de métricas, curva de convergencia e historial por ciclos.
- Reproducción de experimentos mediante semillas pseudoaleatorias.

## 5. Tecnologías utilizadas

| Componente | Tecnologías |
|---|---|
| Backend y API REST | Python, FastAPI, Pydantic |
| Cálculo numérico y optimización | Python, NumPy |
| Frontend | React, TypeScript, Vite |
| Visualización espacial | HTML Canvas 2D |
| Pruebas | Pytest y herramientas de pruebas TypeScript/React |

## 6. Estructura general

```text
ABC Security Camera Optimizer/
├── backend/
│   ├── src/camera_optimizer/
│   │   ├── geometry/       # Operaciones geométricas
│   │   ├── domain/         # Plano, paredes, obstáculos y malla
│   │   ├── camera/         # Parámetros y poses de cámaras
│   │   ├── coverage/       # Cálculo de cobertura
│   │   ├── objective/      # Función objetivo
│   │   ├── optimizer/      # Algoritmo ABC secuencial
│   │   └── api/            # Endpoints FastAPI
│   └── tests/              # Pruebas automatizadas
├── frontend/
│   └── src/                # Interfaz React, editor y Canvas
├── docs/                   # Informes y evidencias visuales
└── README.md
```

## 7. Instalación y ejecución

### Requisitos previos

- Python 3.11 o posterior.
- Node.js y npm compatibles con las versiones declaradas en `frontend/package.json`.

### Iniciar el backend

Desde una terminal, situada en la raíz del proyecto:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m camera_optimizer.main
```

API disponible en: **http://127.0.0.1:8000**  
Documentación interactiva: **http://127.0.0.1:8000/docs**

### Iniciar el frontend

En **otra terminal**, desde la raíz del proyecto:

```bash
cd frontend
npm ci
npm run dev
```

Abrir en el navegador: **http://127.0.0.1:5173**

> En Windows, la activación del entorno virtual de Python es diferente (`.venv\Scripts\activate`).

## 8. Uso básico

1. Abrir la aplicación en el navegador.
2. Seleccionar **Crear escenario** o elegir una de las **plantillas**.
3. Dibujar o modificar paredes, aberturas, obstáculos y zonas de riesgo.
4. Establecer la cantidad de cámaras y, si se desea, los parámetros avanzados.
5. Validar el escenario y ejecutar **Optimizar**.
6. Consultar la ubicación propuesta, los mapas de cobertura y los resultados del algoritmo.
7. Abrir **Análisis** para examinar la convergencia y reproducir los ciclos registrados.

## 9. Ejecución de pruebas

**Backend:**

```bash
cd backend
python3 -m pytest tests/ -q
```

**Frontend (desde `frontend/`):**

```bash
npm run test:all
npm run build
npm run lint
```

El proyecto incluye pruebas automatizadas para geometría, cobertura, restricciones, optimización y componentes de la interfaz.

## 10. Alcance y consideraciones

Este es un **proyecto académico de simulación y optimización**. La representación es bidimensional y la probabilidad de detección se calcula con un modelo heurístico. Por tanto, los resultados no sustituyen un levantamiento físico ni una evaluación profesional de seguridad.

El algoritmo ABC es estocástico: la calidad de una solución puede variar con la semilla y los parámetros seleccionados. No se garantiza encontrar el óptimo global en todas las ejecuciones.

---

**Universidad Autónoma de Aguascalientes · Ingeniería en Computación Inteligente · Octubre de 2026**
