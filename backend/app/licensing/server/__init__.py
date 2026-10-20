"""Servicio central de licencias de NEXORA.

Aplicación FastAPI **independiente** de la instalación local. Tiene su propia
configuración, su propia base de datos (``LICENSE_DATABASE_URL``) y su modelo de
datos de licencias, de modo que nunca se mezclan los datos de los supermercados
con la administración comercial.

Se ejecuta, por ejemplo, con::

    uvicorn app.licensing.server.main:app --host 0.0.0.0 --port 8100

La clave privada de firma vive únicamente aquí (o en la herramienta
administrativa). Nunca se incluye en el instalador ni en el frontend.
"""
