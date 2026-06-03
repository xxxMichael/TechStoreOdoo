describe('Configuración: Tipos de Servicio E2E', () => {
  beforeEach(() => {
    cy.login()
  })

  it('Debe crear un nuevo tipo de servicio exitosamente', () => {
    // Abrir la aplicación TechStore de manera robusta
    cy.openTechStoreApp()

    // Navegar a Configuración > Tipos de Servicio
    cy.get('button[data-menu-xmlid="techstore_maintenance.menu_ts_config"]').click({ force: true })
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_service_types"]').click({ force: true })

    // Clic en botón "Crear" (Nuevo)
    cy.get('.o_list_button_add').click()

    // Llenar formulario con un nombre único para evitar errores de validación (unique constraint)
    const uniqueName = `Servicio Cypress E2E ${Date.now()}`
    cy.get('div[name="name"] input').type(uniqueName)
    cy.get('div[name="description"] textarea').type('Este es un servicio creado automáticamente por Cypress.')

    // Guardar (Odoo 16 auto-guarda al salir del campo o con el botón guardar manual)
    cy.get('.o_form_button_save').click({ force: true })

    // Verificar guardado (Odoo 16 mantiene el modo edición, así que el texto es un 'value' del input)
    cy.get('div[name="name"] input').should('have.value', uniqueName)
  })
})
