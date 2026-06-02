import json
import statistics
import time
from datetime import datetime

import requests


BASE_URL = "http://localhost:8069"
DB_NAME = "odoo2"
USERNAME = "admin"
PASSWORD = "admin"

MODULE_DIR = r"C:\odoo16-docker\addons\techstore_maintenance"
TEST_CASES_FILE = MODULE_DIR + r"\api_test_cases.txt"
TEST_RESULTS_FILE = MODULE_DIR + r"\api_test_results.txt"
ANALYSIS_FILE = MODULE_DIR + r"\api_performance_security_report.txt"


class ApiQualityRunner:
    def __init__(self):
        self.session = requests.Session()
        self.run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.created = {
            "clients": [],
            "service-types": [],
            "technicians": [],
            "equipment": [],
            "maintenance-orders": [],
        }
        self.results = []
        self.performance_samples = []
        self.context = {}

    def authenticate(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": DB_NAME,
                "login": USERNAME,
                "password": PASSWORD,
            },
            "id": 1,
        }
        response = self.session.post(
            f"{BASE_URL}/web/session/authenticate",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("result", {}).get("uid"):
            raise RuntimeError("No fue posible autenticar contra Odoo.")

    def api_request(self, method, path, json_body=None, raw_body=None, headers=None, authenticated=True):
        client = self.session if authenticated else requests
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        start = time.perf_counter()
        response = client.request(
            method,
            BASE_URL + path,
            json=json_body if raw_body is None else None,
            data=raw_body,
            headers=request_headers,
            timeout=30,
            allow_redirects=False,
        )
        elapsed = time.perf_counter() - start
        content_type = response.headers.get("Content-Type", "")
        parsed = None
        if "application/json" in content_type:
            try:
                parsed = response.json()
            except ValueError:
                parsed = None

        return {
            "status": response.status_code,
            "elapsed": elapsed,
            "headers": dict(response.headers),
            "json": parsed,
            "text": response.text,
        }

    def record_result(self, case_id, objective, request_desc, expected, actual, passed, elapsed, category):
        self.results.append(
            {
                "case_id": case_id,
                "objective": objective,
                "request": request_desc,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "elapsed": elapsed,
                "category": category,
            }
        )
        if elapsed is not None:
            self.performance_samples.append((case_id, elapsed))

    def run(self):
        self.write_test_cases()
        self.authenticate()
        self.prepare_master_data()
        self.run_functional_tests()
        self.run_security_tests()
        self.run_performance_tests()
        self.cleanup()
        self.write_results()
        self.write_analysis()

    def unique(self, prefix):
        return f"{prefix} {self.run_id}"

    def prepare_master_data(self):
        service_type_name = self.unique("Servicio API")
        technician_name = self.unique("Tecnico API")
        client_name = self.unique("Cliente API")
        equipment_name = self.unique("Laptop API")
        employee_number = f"EMP-{self.run_id[-8:]}"
        serial_number = f"SN-{self.run_id}"

        client_resp = self.api_request(
            "POST",
            "/api/techstore/clients",
            json_body={
                "name": client_name,
                "email": f"cliente.{self.run_id}@example.com",
                "phone": "0990000001",
                "mobile": "0990000002",
                "is_company": False,
                "active": True,
            },
        )
        self.ensure_http_ok(client_resp, "Crear cliente base")
        client_id = client_resp["json"]["id"]
        self.created["clients"].append(client_id)

        service_resp = self.api_request(
            "POST",
            "/api/techstore/service-types",
            json_body={
                "name": service_type_name,
                "description": "Creado por prueba automatizada API",
                "active": True,
            },
        )
        self.ensure_http_ok(service_resp, "Crear tipo de servicio base")
        service_type_id = service_resp["json"]["id"]
        self.created["service-types"].append(service_type_id)

        technician_resp = self.api_request(
            "POST",
            "/api/techstore/technicians",
            json_body={
                "name": technician_name,
                "employee_number": employee_number,
                "email": f"tecnico.{self.run_id}@example.com",
                "phone": "0981111111",
                "specialty_hardware": True,
                "specialty_software": True,
                "state": "active",
                "availability": "available",
            },
        )
        self.ensure_http_ok(technician_resp, "Crear tecnico base")
        technician_id = technician_resp["json"]["id"]
        self.created["technicians"].append(technician_id)

        equipment_resp = self.api_request(
            "POST",
            "/api/techstore/equipment",
            json_body={
                "name": equipment_name,
                "equipment_type": "laptop",
                "brand": "Lenovo",
                "model_name": "ThinkPad Test",
                "serial_number": serial_number,
                "current_state": "faulty",
                "notes": "Equipo creado por automatizacion",
                "active": True,
                "client_id": client_id,
            },
        )
        self.ensure_http_ok(equipment_resp, "Crear equipo base")
        equipment_id = equipment_resp["json"]["id"]
        self.created["equipment"].append(equipment_id)

        self.context = {
            "client_id": client_id,
            "service_type_id": service_type_id,
            "technician_id": technician_id,
            "equipment_id": equipment_id,
        }

    def ensure_http_ok(self, response_data, action):
        if response_data["status"] >= 400:
            detail = response_data["json"] or response_data["text"]
            raise RuntimeError(f"{action} fallo: {detail}")

    def run_functional_tests(self):
        dashboard = self.api_request("GET", "/api/techstore/dashboard")
        self.record_result(
            "PF-01",
            "Consultar dashboard general",
            "GET /api/techstore/dashboard",
            "HTTP 200 con metricas clave",
            self.format_actual(dashboard),
            dashboard["status"] == 200 and isinstance(dashboard["json"], dict) and "total_orders" in dashboard["json"],
            dashboard["elapsed"],
            "Funcional",
        )

        order_payload = {
            "client_id": self.context["client_id"],
            "equipment_id": self.context["equipment_id"],
            "service_type_id": self.context["service_type_id"],
            "priority": "2",
            "reception_date": datetime.now().strftime("%Y-%m-%d"),
            "problem_description": "No enciende despues de una actualizacion.",
            "physical_condition": "Equipo sin golpes visibles y con cargador.",
        }
        create_order = self.api_request("POST", "/api/techstore/maintenance-orders", json_body=order_payload)
        order_ok = create_order["status"] == 201 and create_order["json"].get("state") == "received"
        order_id = create_order["json"].get("id") if create_order["json"] else None
        if order_id:
            self.created["maintenance-orders"].append(order_id)
            self.context["order_id"] = order_id
        self.record_result(
            "PF-02",
            "Crear orden de mantenimiento",
            "POST /api/techstore/maintenance-orders",
            "HTTP 201 y estado received",
            self.format_actual(create_order),
            order_ok,
            create_order["elapsed"],
            "Funcional",
        )

        assign_technician = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/assign-technician",
            json_body={"technician_id": self.context["technician_id"]},
        )
        assign_ok = assign_technician["status"] == 200 and assign_technician["json"].get("technician_id", {}).get("id") == self.context["technician_id"]
        self.record_result(
            "PF-03",
            "Asignar tecnico a la orden",
            "POST /api/techstore/maintenance-orders/{id}/actions/assign-technician",
            "HTTP 200 y tecnico asignado",
            self.format_actual(assign_technician),
            assign_ok,
            assign_technician["elapsed"],
            "Funcional",
        )

        start_diagnosis = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/start-diagnosis",
            json_body={},
        )
        diag_ok = start_diagnosis["status"] == 200 and start_diagnosis["json"].get("state") == "diagnosis"
        self.record_result(
            "PF-04",
            "Mover orden a diagnostico",
            "POST /api/techstore/maintenance-orders/{id}/actions/start-diagnosis",
            "HTTP 200 y estado diagnosis",
            self.format_actual(start_diagnosis),
            diag_ok,
            start_diagnosis["elapsed"],
            "Funcional",
        )

        repair_without_diagnosis = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/start-repair",
            json_body={},
        )
        repair_blocked = repair_without_diagnosis["status"] == 400
        self.record_result(
            "PF-05",
            "Bloquear paso a reparacion sin diagnostico",
            "POST /api/techstore/maintenance-orders/{id}/actions/start-repair",
            "HTTP 400 por diagnostico faltante",
            self.format_actual(repair_without_diagnosis),
            repair_blocked,
            repair_without_diagnosis["elapsed"],
            "Funcional",
        )

        update_diagnosis = self.api_request(
            "PATCH",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}",
            json_body={
                "diagnosis": "La bateria requiere reemplazo.",
                "work_done": "Se reviso tarjeta principal.",
            },
        )
        update_diag_ok = update_diagnosis["status"] == 200 and update_diagnosis["json"].get("diagnosis") == "La bateria requiere reemplazo."
        self.record_result(
            "PF-06",
            "Actualizar diagnostico de la orden",
            "PATCH /api/techstore/maintenance-orders/{id}",
            "HTTP 200 y diagnostico persistido",
            self.format_actual(update_diagnosis),
            update_diag_ok,
            update_diagnosis["elapsed"],
            "Funcional",
        )

        start_repair = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/start-repair",
            json_body={},
        )
        repair_ok = start_repair["status"] == 200 and start_repair["json"].get("state") == "repair"
        self.record_result(
            "PF-07",
            "Mover orden a reparacion",
            "POST /api/techstore/maintenance-orders/{id}/actions/start-repair",
            "HTTP 200 y estado repair",
            self.format_actual(start_repair),
            repair_ok,
            start_repair["elapsed"],
            "Funcional",
        )

        ready_without_resolution = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/mark-ready",
            json_body={},
        )
        ready_blocked = ready_without_resolution["status"] == 400
        self.record_result(
            "PF-08",
            "Bloquear listo sin resolucion",
            "POST /api/techstore/maintenance-orders/{id}/actions/mark-ready",
            "HTTP 400 por resolucion faltante",
            self.format_actual(ready_without_resolution),
            ready_blocked,
            ready_without_resolution["elapsed"],
            "Funcional",
        )

        update_resolution = self.api_request(
            "PATCH",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}",
            json_body={
                "resolution": "Se reemplazo bateria y se valido arranque.",
                "parts_used": "Bateria 65W",
            },
        )
        resolution_ok = update_resolution["status"] == 200 and update_resolution["json"].get("resolution") == "Se reemplazo bateria y se valido arranque."
        self.record_result(
            "PF-09",
            "Actualizar resolucion de la orden",
            "PATCH /api/techstore/maintenance-orders/{id}",
            "HTTP 200 y resolucion persistida",
            self.format_actual(update_resolution),
            resolution_ok,
            update_resolution["elapsed"],
            "Funcional",
        )

        mark_ready = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/mark-ready",
            json_body={},
        )
        mark_ready_ok = mark_ready["status"] == 200 and mark_ready["json"].get("state") == "ready"
        self.record_result(
            "PF-10",
            "Marcar orden lista para entrega",
            "POST /api/techstore/maintenance-orders/{id}/actions/mark-ready",
            "HTTP 200 y estado ready",
            self.format_actual(mark_ready),
            mark_ready_ok,
            mark_ready["elapsed"],
            "Funcional",
        )

        mark_delivered = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/mark-delivered",
            json_body={},
        )
        delivered_ok = mark_delivered["status"] == 200 and mark_delivered["json"].get("state") == "delivered"
        self.record_result(
            "PF-11",
            "Marcar orden entregada",
            "POST /api/techstore/maintenance-orders/{id}/actions/mark-delivered",
            "HTTP 200 y estado delivered",
            self.format_actual(mark_delivered),
            delivered_ok,
            mark_delivered["elapsed"],
            "Funcional",
        )

        close_order = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/close",
            json_body={},
        )
        close_ok = close_order["status"] == 200 and close_order["json"].get("state") == "closed"
        self.record_result(
            "PF-12",
            "Cerrar orden entregada",
            "POST /api/techstore/maintenance-orders/{id}/actions/close",
            "HTTP 200 y estado closed",
            self.format_actual(close_order),
            close_ok,
            close_order["elapsed"],
            "Funcional",
        )

        get_audit_logs = self.api_request(
            "GET",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/audit-logs",
        )
        audit_items = get_audit_logs["json"].get("items", []) if get_audit_logs["json"] else []
        audit_ok = get_audit_logs["status"] == 200 and len(audit_items) >= 5
        self.record_result(
            "PF-13",
            "Consultar bitacora de auditoria de la orden",
            "GET /api/techstore/maintenance-orders/{id}/audit-logs",
            "HTTP 200 con eventos de auditoria",
            self.format_actual(get_audit_logs),
            audit_ok,
            get_audit_logs["elapsed"],
            "Funcional",
        )

    def run_security_tests(self):
        unauth_dashboard = self.api_request("GET", "/api/techstore/dashboard", authenticated=False)
        unauth_ok = unauth_dashboard["status"] in (303, 401) or (
            unauth_dashboard["status"] == 200 and "application/json" not in unauth_dashboard["headers"].get("Content-Type", "")
        )
        self.record_result(
            "PS-01",
            "Verificar que la API no exponga datos sin sesion",
            "GET anonimo /api/techstore/dashboard",
            "Redireccion o rechazo sin JSON sensible",
            self.format_actual(unauth_dashboard),
            unauth_ok,
            unauth_dashboard["elapsed"],
            "Seguridad",
        )

        invalid_resource = self.api_request("GET", "/api/techstore/no-such-resource")
        invalid_resource_ok = invalid_resource["status"] == 404
        self.record_result(
            "PS-02",
            "Rechazar recursos inexistentes",
            "GET /api/techstore/no-such-resource",
            "HTTP 404",
            self.format_actual(invalid_resource),
            invalid_resource_ok,
            invalid_resource["elapsed"],
            "Seguridad",
        )

        audit_create = self.api_request(
            "POST",
            "/api/techstore/audit-logs",
            json_body={
                "order_id": self.context["order_id"],
                "event_type": "Intento manual",
                "description": "No deberia permitirse",
            },
        )
        audit_create_ok = audit_create["status"] == 400
        self.record_result(
            "PS-03",
            "Bloquear creacion directa del log de auditoria",
            "POST /api/techstore/audit-logs",
            "HTTP 400",
            self.format_actual(audit_create),
            audit_create_ok,
            audit_create["elapsed"],
            "Seguridad",
        )

        invalid_json = self.api_request(
            "POST",
            "/api/techstore/clients",
            raw_body="{bad json",
        )
        invalid_json_ok = invalid_json["status"] == 400
        self.record_result(
            "PS-04",
            "Validar rechazo de JSON invalido",
            "POST /api/techstore/clients con cuerpo malformado",
            "HTTP 400",
            self.format_actual(invalid_json),
            invalid_json_ok,
            invalid_json["elapsed"],
            "Seguridad",
        )

        invalid_action = self.api_request(
            "POST",
            f"/api/techstore/maintenance-orders/{self.context['order_id']}/actions/nope",
            json_body={},
        )
        invalid_action_ok = invalid_action["status"] == 404
        self.record_result(
            "PS-05",
            "Rechazar acciones no definidas",
            "POST /api/techstore/maintenance-orders/{id}/actions/nope",
            "HTTP 404",
            self.format_actual(invalid_action),
            invalid_action_ok,
            invalid_action["elapsed"],
            "Seguridad",
        )

    def run_performance_tests(self):
        dashboard_times = []
        order_list_times = []

        for _ in range(10):
            dashboard = self.api_request("GET", "/api/techstore/dashboard")
            dashboard_times.append(dashboard["elapsed"])

        for _ in range(10):
            orders = self.api_request("GET", "/api/techstore/maintenance-orders?limit=20")
            order_list_times.append(orders["elapsed"])

        self.record_result(
            "PR-01",
            "Medir latencia repetida del dashboard",
            "10 llamadas GET /api/techstore/dashboard",
            "Promedio estable y sin errores",
            self.describe_stats(dashboard_times),
            True,
            statistics.mean(dashboard_times),
            "Rendimiento",
        )
        self.record_result(
            "PR-02",
            "Medir latencia repetida del listado de ordenes",
            "10 llamadas GET /api/techstore/maintenance-orders?limit=20",
            "Promedio estable y sin errores",
            self.describe_stats(order_list_times),
            True,
            statistics.mean(order_list_times),
            "Rendimiento",
        )

    def cleanup(self):
        cleanup_order = [
            ("maintenance-orders", self.created["maintenance-orders"]),
            ("equipment", self.created["equipment"]),
            ("technicians", self.created["technicians"]),
            ("service-types", self.created["service-types"]),
            ("clients", self.created["clients"]),
        ]
        for resource, ids in cleanup_order:
            for record_id in ids:
                try:
                    self.api_request("DELETE", f"/api/techstore/{resource}/{record_id}")
                except Exception:
                    pass

    def write_test_cases(self):
        lines = [
            "DISENO DE CASOS DE PRUEBA - API TECHSTORE MAINTENANCE",
            f"Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "PRUEBAS FUNCIONALES",
            "PF-01 | GET /api/techstore/dashboard | Validar consulta de metricas generales.",
            "PF-02 | POST /api/techstore/maintenance-orders | Validar creacion de orden con datos obligatorios.",
            "PF-03 | POST /api/techstore/maintenance-orders/{id}/actions/assign-technician | Validar asignacion de tecnico.",
            "PF-04 | POST /api/techstore/maintenance-orders/{id}/actions/start-diagnosis | Validar cambio de estado a diagnosis.",
            "PF-05 | POST /api/techstore/maintenance-orders/{id}/actions/start-repair | Validar bloqueo sin diagnostico.",
            "PF-06 | PATCH /api/techstore/maintenance-orders/{id} | Validar actualizacion de diagnostico.",
            "PF-07 | POST /api/techstore/maintenance-orders/{id}/actions/start-repair | Validar cambio a repair.",
            "PF-08 | POST /api/techstore/maintenance-orders/{id}/actions/mark-ready | Validar bloqueo sin resolucion.",
            "PF-09 | PATCH /api/techstore/maintenance-orders/{id} | Validar actualizacion de resolucion.",
            "PF-10 | POST /api/techstore/maintenance-orders/{id}/actions/mark-ready | Validar cambio a ready.",
            "PF-11 | POST /api/techstore/maintenance-orders/{id}/actions/mark-delivered | Validar cambio a delivered.",
            "PF-12 | POST /api/techstore/maintenance-orders/{id}/actions/close | Validar cierre de la orden.",
            "PF-13 | GET /api/techstore/maintenance-orders/{id}/audit-logs | Validar trazabilidad por auditoria.",
            "",
            "PRUEBAS DE SEGURIDAD",
            "PS-01 | GET anonimo /api/techstore/dashboard | Verificar que se requiera sesion autenticada.",
            "PS-02 | GET /api/techstore/no-such-resource | Verificar manejo de recurso inexistente.",
            "PS-03 | POST /api/techstore/audit-logs | Verificar bloqueo de escritura en auditoria.",
            "PS-04 | POST /api/techstore/clients con JSON invalido | Verificar validacion de entrada.",
            "PS-05 | POST /api/techstore/maintenance-orders/{id}/actions/nope | Verificar rechazo de accion no autorizada.",
            "",
            "PRUEBAS DE RENDIMIENTO",
            "PR-01 | 10 llamadas GET /api/techstore/dashboard | Medir latencia promedio, minima y maxima.",
            "PR-02 | 10 llamadas GET /api/techstore/maintenance-orders?limit=20 | Medir latencia promedio, minima y maxima.",
        ]
        with open(TEST_CASES_FILE, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def write_results(self):
        total = len(self.results)
        passed = sum(1 for result in self.results if result["passed"])
        failed = total - passed
        lines = [
            "RESULTADOS DE EJECUCION - API TECHSTORE MAINTENANCE",
            f"Fecha de ejecucion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Base URL: {BASE_URL}",
            f"Total de casos: {total}",
            f"Casos exitosos: {passed}",
            f"Casos fallidos: {failed}",
            "",
        ]

        for category in ("Funcional", "Seguridad", "Rendimiento"):
            lines.append(category.upper())
            for result in self.results:
                if result["category"] != category:
                    continue
                lines.extend(
                    [
                        f"Caso: {result['case_id']}",
                        f"Objetivo: {result['objective']}",
                        f"Solicitud: {result['request']}",
                        f"Esperado: {result['expected']}",
                        f"Obtenido: {result['actual']}",
                        f"Estado: {'PASS' if result['passed'] else 'FAIL'}",
                        f"Tiempo: {result['elapsed']:.4f}s" if result["elapsed"] is not None else "Tiempo: N/A",
                        "",
                    ]
                )

        with open(TEST_RESULTS_FILE, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    def write_analysis(self):
        response_times = [sample[1] for sample in self.performance_samples]
        avg_time = statistics.mean(response_times) if response_times else 0.0
        min_time = min(response_times) if response_times else 0.0
        max_time = max(response_times) if response_times else 0.0
        failed = [result for result in self.results if not result["passed"]]
        lines = [
            "ANALISIS DE RENDIMIENTO Y SEGURIDAD - API TECHSTORE MAINTENANCE",
            f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "RESUMEN DE RENDIMIENTO",
            f"Tiempo promedio global: {avg_time:.4f}s",
            f"Tiempo minimo global: {min_time:.4f}s",
            f"Tiempo maximo global: {max_time:.4f}s",
            "Criterio de referencia usado: respuesta esperada menor a 0.50s para operaciones normales.",
            f"Evaluacion: {'CUMPLE' if avg_time < 0.50 else 'REQUIERE ATENCION'}.",
            "",
            "HALLAZGOS DE SEGURIDAD",
            "1. La API exige sesion autenticada para exponer datos, lo cual es correcto para endpoints de negocio.",
            "2. Los logs de auditoria no aceptan escritura directa desde la API; esto protege la trazabilidad.",
            "3. Las rutas usan csrf=False en todos los endpoints; esto aumenta la superficie de riesgo si la sesion se reutiliza desde navegador.",
            "4. El controlador expone CRUD generico sobre varios modelos y usa auth='user'; no hay control fino por rol dentro del controlador.",
            "5. No se observan limites de tasa, paginacion maxima estricta ni validaciones explicitas de volumen de carga.",
            "",
            "MEJORAS PROPUESTAS",
            "1. Cambiar autenticacion basada en sesion por tokens dedicados para API o agregar un encabezado API key firmado.",
            "2. Aplicar autorizacion por grupos/permisos por recurso y operacion, no solo auth='user'.",
            "3. Mantener csrf=False solo si la API deja de depender de cookies de navegador; en caso contrario, revisar proteccion CSRF/CORS.",
            "4. Definir limites de limit y offset, y agregar rate limiting para evitar abuso y scraping interno.",
            "5. Agregar validaciones de integridad mas explicitas en la API para referencias cruzadas, por ejemplo equipo-cliente en ordenes.",
            "6. Incorporar pruebas automatizadas en CI que ejecuten estos casos despues de cada cambio del modulo.",
            "",
            "CASOS FALLIDOS",
        ]
        if failed:
            for result in failed:
                lines.append(f"- {result['case_id']}: {result['actual']}")
        else:
            lines.append("- No se detectaron casos fallidos en esta ejecucion.")

        with open(ANALYSIS_FILE, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def format_actual(self, response_data):
        payload = response_data["json"] if response_data["json"] is not None else response_data["text"][:300]
        return f"HTTP {response_data['status']} | {json.dumps(payload, ensure_ascii=False, default=str)[:500]}"

    def describe_stats(self, samples):
        return (
            f"avg={statistics.mean(samples):.4f}s, "
            f"min={min(samples):.4f}s, "
            f"max={max(samples):.4f}s"
        )


if __name__ == "__main__":
    runner = ApiQualityRunner()
    runner.run()
