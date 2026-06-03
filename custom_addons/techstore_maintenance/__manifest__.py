# -*- coding: utf-8 -*-
{
    'name': 'TechStore Maintenance',
    'version': '16.0.1.0.0',
    'summary': 'Sistema de Gestión de Mantenimientos Técnicos — TechStore',
    'description': """
        Módulo para la gestión integral de órdenes de mantenimiento técnico,
        equipos de clientes, técnicos especializados y métricas de calidad
        alineadas con ISO/IEC 25010.
    """,
    'author': 'TechStore — Proyecto Integrador GCS',
    'category': 'Services/Maintenance',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'hr',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/service_type_data.xml',
        'views/service_type_views.xml',
        'views/technician_views.xml',
        'views/equipment_views.xml',
        'views/maintenance_order_views.xml',
        'views/dashboard_views.xml',
        'report/maintenance_order_report.xml',
        'views/menu_views.xml',
    ],


    'installable': True,
    'application': True,
    'auto_install': False,

    'images': ['static/description/icon.png'],
}
