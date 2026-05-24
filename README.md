# TechStore Maintenance — Sistema de Gestión de Mantenimientos Técnicos

Módulo personalizado de Odoo 16 para la gestión de órdenes de mantenimiento técnico de TechStore.

## 🚀 Inicio rápido

### Requisitos previos
- Docker Desktop instalado y corriendo
- Git

### Levantar el entorno

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd ProyectoFinal

# 2. Copiar el archivo de entorno
cp .env.example .env

# 3. Levantar los contenedores
docker-compose up -d

# 4. Acceder a Odoo
# http://localhost:8069
# Usuario: admin | Contraseña: admin
```

### Instalar el módulo

1. Activar el **Modo Desarrollador** en Ajustes → Configuración técnica
2. Ir a **Aplicaciones → Actualizar lista de aplicaciones**
3. Buscar `TechStore Maintenance` e instalar

## 📁 Estructura del proyecto

```
ProyectoFinal/
├── .devcontainer/
│   └── devcontainer.json        # Configuración VS Code DevContainer
├── custom_addons/
│   └── techstore_maintenance/   # Módulo personalizado principal
│       ├── models/              # Modelos de datos (Python)
│       ├── views/               # Vistas XML (formularios, listas, kanban)
│       ├── security/            # Roles y permisos de acceso
│       ├── data/                # Datos iniciales del catálogo
│       └── static/              # Recursos estáticos (icono del módulo)
├── .env                         # Variables de entorno (no subir a git)
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore
├── docker-compose.yml           # Orquestación Docker (Odoo 16 + PostgreSQL 15)
└── odoo.conf                    # Configuración de Odoo
```

## 🗃️ Modelos del módulo

| Modelo | Descripción |
|--------|-------------|
| `ts.maintenance.order` | Orden de mantenimiento (entidad central) |
| `ts.equipment` | Equipo tecnológico del cliente |
| `ts.technician` | Técnico con especialidades y métricas |
| `ts.service.type` | Catálogo de tipos de servicio |
| `ts.audit.log` | Registro inmutable de cambios |

## 🔄 Estados de una orden

```
Recibido → En Diagnóstico → En Reparación → Listo para Entrega → Entregado → Cerrado
```

## 👥 Roles del sistema

| Rol | Descripción |
|-----|-------------|
| `Administrador TechStore` | Acceso total |
| `Supervisor de Taller` | Gestión completa de órdenes y técnicos |
| `Técnico` | Ver y actualizar sus propias órdenes |
| `Recepcionista` | Crear órdenes y registrar clientes/equipos |

## 🛠️ Comandos útiles

```bash
# Ver logs de Odoo
docker-compose logs -f odoo

# Reiniciar Odoo (para recargar módulo)
docker-compose restart odoo

# Actualizar módulo desde consola
docker-compose exec odoo odoo -u techstore_maintenance -d techstore_db --stop-after-init

# Acceder a la base de datos
docker-compose exec db psql -U odoo -d techstore_db
```

## 📋 Proyecto académico

**Materia:** Gestión de Calidad del Software  
**Plataforma:** Odoo 16.0 Community Edition  
**Base de datos:** PostgreSQL 15  
**Norma de calidad:** ISO/IEC 25010
