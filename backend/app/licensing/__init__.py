"""Sistema profesional de licencias de NEXORA.

Contiene dos componentes claramente separados:

- ``app.licensing.server``: servicio central administrativo (aplicación FastAPI
  independiente, base de datos propia) que emite y administra licencias.
- ``app.licensing.local``: instalación local del supermercado, que valida y
  almacena su licencia firmada y protege los endpoints de negocio.

El núcleo compartido (``constants``, ``canonical``, ``keys``, ``documents``)
define el formato firmado de licencia y las utilidades criptográficas.
"""
