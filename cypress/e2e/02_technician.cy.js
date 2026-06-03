describe('Técnicos E2E', () => {
  beforeEach(() => {
    cy.login()
  })

  it('Debe registrar un nuevo técnico', () => {
    cy.openTechStoreApp()

    // Navegar a Técnicos > Gestión de Técnicos
    cy.get('button[data-menu-xmlid="techstore_maintenance.menu_ts_technicians_root"]').click({ force: true })
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_technicians"]').click({ force: true })

    // Crear Técnico
    cy.get('.o_list_button_add').click()

    // Llenar campos con identificadores únicos
    const uniqueId = Date.now()
    const uniqueName = `Técnico Cypress E2E ${uniqueId}`
    cy.get('div[name="name"] input').type(uniqueName)
    cy.get('div[name="employee_number"] input').type(`EMP-CY-${uniqueId}`)
    cy.get('div[name="email"] input').type(`cypress${uniqueId}@techstore.test`)
    
    // Guardar
    cy.get('.o_form_button_save').click({ force: true })

    // Verificar guardado
    cy.get('div[name="name"] input').should('have.value', uniqueName)
  })
})
