# ABC Security Camera Optimizer

**Optimización de la ubicación y orientación de cámaras de seguridad mediante el algoritmo Artificial Bee Colony (ABC)**

## Información académica

**Universidad:** Universidad Autónoma de Aguascalientes (UAA)  
**Carrera:** Ingeniería en Computación Inteligente  
**Asignatura:** Paralelización de Algoritmos  
**Fecha:** Octubre de 2026

### Integrantes del equipo

- Carlos Abraham Negrete de la Cruz
- Evelyn Vanessa Campos Aguayo
- Yaretzi Castillo Morales

---

## Descripción del proyecto

ABC Security Camera Optimizer es una aplicación interactiva desarrollada para optimizar la ubicación y orientación de cámaras de seguridad en escenarios arquitectónicos bidimensionales.

El sistema utiliza el algoritmo **Artificial Bee Colony (ABC)** para explorar distintas configuraciones de cámaras y encontrar soluciones que mejoren la cobertura del recinto, considerando obstáculos, paredes, campos de visión y zonas prioritarias.

## Planteamiento del problema

La instalación de cámaras de seguridad presenta desafíos relacionados con la existencia de puntos ciegos, obstáculos físicos y distribuciones poco eficientes.

El problema consiste en encontrar las posiciones y orientaciones de un número determinado de cámaras que permitan mejorar la vigilancia del espacio, priorizando las regiones de mayor importancia.

## Algoritmo Artificial Bee Colony

Artificial Bee Colony es una metaheurística inspirada en el comportamiento de búsqueda de alimento de las abejas.

Su funcionamiento comprende tres fases principales:

1. **Abejas empleadas:** generan soluciones vecinas y exploran mejoras.
2. **Abejas observadoras:** seleccionan configuraciones según su aptitud y buscan nuevas soluciones.
3. **Abejas exploradoras:** reemplazan soluciones estancadas para favorecer la exploración del espacio de búsqueda.

En este proyecto, cada solución representa las coordenadas y orientaciones de las cámaras de seguridad.

**La implementación del algoritmo es estrictamente secuencial.**

## Objetivo del proyecto

Diseñar e implementar un sistema que permita optimizar la distribución de cámaras de seguridad mediante ABC, utilizando una función objetivo que considere la cobertura probabilística ponderada por riesgo y el déficit de protección en zonas críticas.

## Funcionalidades principales

- Creación y edición de escenarios arquitectónicos 2D.
- Incorporación de paredes, puertas, obstáculos y zonas de riesgo.
- Optimización automática de posiciones y orientaciones de cámaras.
- Visualización de cobertura geométrica y probabilística.
- Mapas de calor calculados por el backend.
- Gráficas de convergencia del algoritmo.
- Reproducción de los ciclos de optimización.
- Importación y exportación de escenarios JSON.

## Tecnologías utilizadas

| Componente | Tecnología |
|---|---|
| Algoritmo y cálculo numérico | Python, NumPy |
| Backend | FastAPI, Pydantic |
| Frontend | React, TypeScript, Vite |
| Visualización | HTML Canvas 2D |
| Pruebas | Pytest y herramientas de pruebas TypeScript/React |

## Instalación y ejecución

Se requiere Python 3.11 o posterior, Node.js y npm compatibles con las dependencias del proyecto.

**Backend:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m camera_optimizer.main
```

**Frontend (en otra terminal):**

```bash
cd frontend
npm ci
npm run dev
```

Abrir la aplicación en:

`http://127.0.0.1:5173`

## Alcance

La aplicación utiliza un modelo bidimensional y probabilidades de detección simuladas matemáticamente. Los resultados son aproximaciones computacionales y no sustituyen una evaluación profesional de seguridad.

El algoritmo ABC es estocástico, por lo que no garantiza alcanzar el óptimo global en todas las ejecuciones.

---

**Universidad Autónoma de Aguascalientes — Ingeniería en Computación Inteligente — Octubre de 2026**
