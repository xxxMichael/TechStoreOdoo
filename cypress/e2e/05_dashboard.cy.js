describe('Dashboard y Análisis E2E', () => {
  beforeEach(() => {
    cy.login()
  })

  it('Debe renderizar el dashboard principal', () => {
    cy.openTechStoreApp()

    // Dashboard principal action link
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_dashboard"]').click({ force: true })

    // Verificar control panel
    cy.get('.o_control_panel').should('be.visible')
  })

  it('Debe renderizar la vista de análisis y gráficas', () => {
    cy.openTechStoreApp()

    // Navegar a Análisis
    cy.get('button[data-menu-xmlid="techstore_maintenance.menu_ts_maintenance"]').click({ force: true })
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_order_analysis"]').click({ force: true })

    // Verificar que exista elemento gráfico (Odoo usa un canvas para Chart.js o d3)
    cy.get('.o_graph_view').should('be.visible')
  })
})
