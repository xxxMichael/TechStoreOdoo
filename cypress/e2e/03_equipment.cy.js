describe('Equipos E2E', () => {
  beforeEach(() => {
    cy.login()
  })

  it('Debe registrar un nuevo equipo', () => {
    cy.openTechStoreApp()

    // Navegar a Equipos > Catálogo de Equipos
    cy.get('button[data-menu-xmlid="techstore_maintenance.menu_ts_equipment_root"]').click({ force: true })
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_equipment"]').click({ force: true })

    // Crear Equipo
    cy.get('.o_list_button_add').click()

    // Llenar campos con variables únicas
    const uniqueId = Date.now()
    const uniqueName = `Laptop Cypress E2E ${uniqueId}`
    cy.get('div[name="name"] input').type(uniqueName)
    cy.get('div[name="equipment_type"] select').select('Laptop')
    cy.get('div[name="brand"] input').type('CypressBrand')
    cy.get('div[name="model_name"] input').type('Cy-2026')
    cy.get('div[name="serial_number"] input').type(`SN-CYPRESS-${uniqueId}`)
    
    // Seleccionar primer cliente (Many2One)
    cy.get('div[name="client_id"] input').click()
    cy.get('ul.ui-autocomplete:visible li a').first().click()

    // Guardar
    cy.get('.o_form_button_save').click({ force: true })

    // Verificar guardado
    cy.get('div[name="name"] input').should('have.value', uniqueName)
  })
})
