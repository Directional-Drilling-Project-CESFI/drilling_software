"""Correção de trajetória e otimização de trajetória Tipo 1.

O aplicativo desktop expõe três módulos independentes:

* ``drilling.features.well_path`` — correção de trajetória 3D (Casos 1–3).
* ``drilling.features.minimization`` — otimização de trajetória Tipo 1 em 2D.
* ``drilling.features.operational_window`` — janela operacional a partir do perfil sônico.

Os núcleos matemáticos ficam nesses pacotes. Tipos, parse e envelopes de
dados ficam em ``drilling.core``. A casca Qt fica em ``drilling.gui``.
"""
