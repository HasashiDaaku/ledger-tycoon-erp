import { useState, useEffect } from 'react'
import './App.css'
import { AnalyticsDashboard } from './AnalyticsDashboard'
import { GeneralLedgerTable } from './components/GeneralLedgerTable'
import { JournalEntriesTable } from './components/JournalEntriesTable'
import { MarketIntelligence } from './components/MarketIntelligence'
import { CollapsiblePanel } from './components/CollapsiblePanel'
import { EventDecisionModal } from './components/EventDecisionModal'
import type { GameState, Account, Product, FinancialMetrics, InventoryItem, LogEntry } from './types/index'

const API_URL = 'http://localhost:8000'

interface DecisionEvent {
  id: number;
  title: string;
  description: string;
  choices: Array<{
    id: string;
    label: string;
    description: string;
    effects: Record<string, any>;
  }>;
  deadline_month: number;
  deadline_year: number;
}

function App() {
  const [gameStarted, setGameStarted] = useState(false)
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [metrics, setMetrics] = useState<FinancialMetrics | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'pricing' | 'inventory' | 'reports' | 'logs' | 'analytics' | 'market'>('dashboard')
  const [pendingEvents, setPendingEvents] = useState<DecisionEvent[]>([])

  const startGame = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/game/start`, {
        method: 'POST'
      })
      const data = await response.json()
      console.log('Game started:', data)
      setGameStarted(true)
      await loadGameState()
      await loadAccounts()
      await loadProducts()
      await loadInventory()
      await loadMetrics()
    } catch (error) {
      console.error('Error starting game:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadGameState = async () => {
    try {
      const response = await fetch(`${API_URL}/game/state`)
      const data = await response.json()
      setGameState(data)
    } catch (error) {
      console.error('Error loading game state:', error)
    }
  }

  const loadAccounts = async () => {
    try {
      // Use the General Ledger endpoint. Assuming Player Company ID is 1.
      // In a real app, we'd get this from context or auth.
      const response = await fetch(`${API_URL}/ledger/general-ledger/1`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json()
      // Ensure data is an array before setting
      if (Array.isArray(data)) {
        setAccounts(data)
      } else {
        console.error('Expected array for accounts, got:', data)
        setAccounts([])
      }
    } catch (error) {
      console.error('Error loading accounts:', error)
      setAccounts([])
    }
  }

  const loadProducts = async () => {
    try {
      const response = await fetch(`${API_URL}/game/products`)
      const data = await response.json()
      setProducts(data)
    } catch (error) {
      console.error('Error loading products:', error)
    }
  }

  const loadMetrics = async () => {
    try {
      const response = await fetch(`${API_URL}/ledger/metrics`)
      if (response.ok) {
        const data = await response.json()
        setMetrics(data)
      } else {
        console.warn("Metrics endpoint not found or error, skipping.")
      }
    } catch (error) {
      console.error('Error loading metrics:', error)
    }
  }

  const loadInventory = async () => {
    try {
      const response = await fetch(`${API_URL}/game/inventory`)
      const data = await response.json()
      setInventory(data)
    } catch (error) {
      console.error('Error loading inventory:', error)
    }
  }

  const advanceTurn = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/game/turn`, {
        method: 'POST'
      })
      const data = await response.json()

      // Check if data has logs
      if (data.logs && Array.isArray(data.logs)) {
        setLogs(prev => [{
          month: data.month - 1 === 0 ? 12 : data.month - 1, // The month that just passed
          year: data.month === 1 ? data.year - 1 : data.year,
          lines: data.logs
        }, ...prev])
      }

      await loadGameState()
      await loadAccounts()
      await loadProducts()
      await loadInventory()
      await loadMetrics()
    } catch (error) {
      console.error('Error advancing turn:', error)
    } finally {
      setLoading(false)
    }
  }

  const purchaseInventory = async (productId: number, quantity: number, unitCost: number) => {
    setLoading(true)
    try {
      await fetch(`${API_URL}/game/purchase`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          product_id: productId,
          quantity: quantity,
          unit_cost: unitCost
        })
      })
      await loadGameState()
      await loadAccounts()
      await loadInventory()
    } catch (error) {
      console.error('Error purchasing inventory:', error)
    } finally {
      setLoading(false)
    }
  }

  const setPrice = async (productId: number, price: number) => {
    try {
      await fetch(`${API_URL}/game/set-price?product_id=${productId}&price=${price}`, {
        method: 'POST'
      })
      await loadProducts()
    } catch (error) {
      console.error('Error setting price:', error)
    }
  }

  const updateMarketingBudget = async (percent: number) => {
    try {
      await fetch(`${API_URL}/game/player/marketing?budget_percent=${percent}`, {
        method: 'POST'
      })
      await loadGameState()
    } catch (error) {
      console.error('Error setting marketing budget:', error)
    }
  }

  const checkPendingEvents = async () => {
    try {
      const response = await fetch(`${API_URL}/game/events/pending`)
      const data = await response.json()
      setPendingEvents(data.pending_events || [])
    } catch (error) {
      console.error('Error checking pending events:', error)
    }
  }

  const makeDecision = async (eventId: number, choiceId: string) => {
    try {
      const response = await fetch(`${API_URL}/game/events/${eventId}/decide?choice_id=${choiceId}`, {
        method: 'POST'
      })
      const data = await response.json()
      console.log('Decision made:', data)

      // Remove the event from pending
      setPendingEvents(prev => prev.filter(e => e.id !== eventId))

      // Reload game state to reflect changes
      await loadGameState()
      await loadAccounts()
    } catch (error) {
      console.error('Error making decision:', error)
      throw error
    }
  }

  useEffect(() => {
    // Check if game is already started
    loadGameState().then(() => {
      if (gameState && gameState.companies.length > 0) {
        setGameStarted(true)
        loadAccounts()
        loadProducts()
        loadInventory()
        loadMetrics()
      }
    })
  }, [])

  // Poll for pending decision events
  useEffect(() => {
    if (!gameStarted) return

    // Check immediately
    checkPendingEvents()

    // Then poll every 5 seconds
    const interval = setInterval(checkPendingEvents, 5000)
    return () => clearInterval(interval)
  }, [gameStarted])

  if (!gameStarted) {
    return (
      <div className="app">
        <div className="welcome-screen">
          <h1>Ledger Tycoon</h1>
          <p>A Business Simulation Game</p>
          <button onClick={startGame} disabled={loading}>
            {loading ? 'Starting...' : 'Start New Game'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <h1>Ledger Tycoon</h1>
        <div className="game-info">
          {gameState && (
            <>
              <span>📅 {new Date(gameState.current_year, gameState.current_month - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</span>
              <span>💰 Cash: ${gameState.cash_balance.toLocaleString()}</span>
              {metrics && (
                <span>📊 Net Worth: ${metrics.net_worth.toLocaleString()}</span>
              )}
            </>
          )}
        </div>
      </header>

      <nav className="tabs">
        <button
          className={activeTab === 'dashboard' ? 'active' : ''}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Dashboard
        </button>
        <button
          className={activeTab === 'pricing' ? 'active' : ''}
          onClick={() => setActiveTab('pricing')}
        >
          💵 Pricing
        </button>
        <button
          className={activeTab === 'inventory' ? 'active' : ''}
          onClick={() => setActiveTab('inventory')}
        >
          📦 Inventory
        </button>
        <button
          className={activeTab === 'analytics' ? 'active' : ''}
          onClick={() => setActiveTab('analytics')}
        >
          📈 Analytics
        </button>
        <button
          className={activeTab === 'reports' ? 'active' : ''}
          onClick={() => setActiveTab('reports')}
        >
          📄 Reports
        </button>
        <button
          className={activeTab === 'market' ? 'active' : ''}
          onClick={() => setActiveTab('market')}
        >
          🌍 Market Intel
        </button>
        <button
          className={activeTab === 'logs' ? 'active' : ''}
          onClick={() => setActiveTab('logs')}
        >
          📜 Logs
        </button>
      </nav>

      <main>
        {activeTab === 'dashboard' && (
          <div className="dashboard">
            <section className="panel">
              <h2>Quick Actions</h2>
              <div className="button-group">
                <button onClick={advanceTurn} disabled={loading} className="primary-action">
                  ⏭️ Next Month
                </button>
              </div>

              <h3>Purchase Inventory (100 units)</h3>
              <div className="product-actions">
                {products.length > 0 ? (
                  products.map(product => (
                    <button
                      key={product.id}
                      onClick={() => purchaseInventory(product.id, 100, product.base_cost)}
                      disabled={loading}
                      title={`Buy 100 ${product.name}s at $${product.base_cost} each`}
                    >
                      🛒 {product.name} (${(product.base_cost * 100).toLocaleString()})
                    </button>
                  ))
                ) : (
                  <p className="loading-text">Loading products...</p>
                )}
              </div>
            </section>

            {/* Marketing Strategy Section */}
            <section className="panel" style={{ marginBottom: '20px', borderLeft: '4px solid #FFD700' }}>
              <h2>📢 Marketing Strategy</h2>
              {gameState && gameState.companies.find(c => c.is_player) && (
                (() => {
                  const player = gameState.companies.find(c => c.is_player);
                  const budgetPct = player?.strategy_memory?.marketing_budget_percent || 0;
                  const currentCash = gameState.cash_balance;
                  const estimatedSpend = currentCash * budgetPct;

                  return (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                        <div>
                          <strong>Current Brand Equity: </strong>
                          <span style={{ fontSize: '1.2em', color: '#FFD700' }}>
                            {(player?.brand_equity || 1.0).toFixed(2)}x
                          </span>
                        </div>
                        <div>
                          <strong>Monthly Budget: </strong>
                          <span>{(budgetPct * 100).toFixed(0)}%</span>
                        </div>
                      </div>

                      <div className="budget-control" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <input
                          type="range"
                          min="0"
                          max="0.5"
                          step="0.01"
                          value={budgetPct}
                          onChange={(e) => updateMarketingBudget(parseFloat(e.target.value))}
                          style={{ flex: 1 }}
                        />
                        <span style={{ minWidth: '60px', textAlign: 'right' }}>
                          {(budgetPct * 100).toFixed(0)}%
                        </span>
                      </div>

                      <p className="help-text" style={{ marginTop: '0.5rem' }}>
                        Estimated Spend: <strong>${estimatedSpend.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong> next month.
                        <br />
                        Invest in marketing to grow your Brand Equity and attract more customers.
                      </p>
                    </div>
                  );
                })()
              )}
            </section>

            {/* Companies Section - Always Visible */}
            <section className="panel" style={{ marginBottom: '20px' }}>
              <h2>Companies</h2>
              {gameState && (
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gameState.companies.map(company => (
                      <tr key={company.id} className={company.is_player ? 'player-row' : ''}>
                        <td>{company.name}</td>
                        <td>{company.is_player ? '👤 Player' : '🤖 Bot'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', gridColumn: '1 / -1' }}>
              <CollapsiblePanel
                title="General Ledger (Trial Balance)"
                defaultExpanded={true}
                summary={
                  <span>
                    Total Debits: <strong>${accounts.reduce((sum, a) => ['Asset', 'Expense'].includes(a.type) ? sum + a.balance : sum, 0).toLocaleString()}</strong> |
                    Total Credits: <strong>${accounts.reduce((sum, a) => ['Liability', 'Equity', 'Revenue'].includes(a.type) ? sum + a.balance : sum, 0).toLocaleString()}</strong>
                  </span>
                }
              >
                <GeneralLedgerTable accounts={accounts} />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Chart of Accounts"
                defaultExpanded={false}
                summary={
                  <span>
                    Total Assets: <strong>${accounts.filter(a => a.type === 'Asset').reduce((sum, a) => sum + a.balance, 0).toLocaleString()}</strong>
                  </span>
                }
              >
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Account</th>
                      <th>Type</th>
                      <th className="text-right">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(accounts) && accounts.map(account => (
                      <tr key={account.id}>
                        <td>{account.code}</td>
                        <td>{account.name}</td>
                        <td><span className={`badge badge-${account.type.toLowerCase()}`}>{account.type}</span></td>
                        <td className={`text-right ${account.balance >= 0 ? 'positive' : 'negative'}`}>
                          ${Math.abs(account.balance).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Journal Entries"
                defaultExpanded={false}
                summary={
                  <span>View recent transactions</span>
                }
              >
                <JournalEntriesTable companyId={gameState?.companies.find(c => c.is_player)?.id || 1} />
              </CollapsiblePanel>
            </div>
          </div>
        )}

        {activeTab === 'pricing' && (
          <div className="dashboard">
            <section className="panel pricing-panel">
              <h2>Product Pricing</h2>
              <p className="help-text">Set your selling prices to compete in the market</p>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Cost</th>
                    <th>Your Price</th>
                    <th>Margin</th>
                    <th>Units Sold</th>
                    <th>Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(product => {
                    const margin = ((product.your_price - product.base_cost) / product.your_price * 100)
                    return (
                      <tr key={product.id}>
                        <td><strong>{product.name}</strong></td>
                        <td>${product.base_cost.toFixed(2)}</td>
                        <td>
                          <input
                            type="number"
                            value={product.your_price || ''}
                            onChange={(e) => setPrice(product.id, parseFloat(e.target.value))}
                            step="0.01"
                            min={product.base_cost}
                            className="price-input"
                          />
                        </td>
                        <td className={margin > 30 ? 'positive' : margin > 15 ? '' : 'negative'}>
                          {margin.toFixed(1)}%
                        </td>
                        <td>{product.units_sold}</td>
                        <td>${product.revenue.toLocaleString()}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </section>
          </div>
        )}

        {activeTab === 'inventory' && (
          <div className="dashboard">
            <section className="panel">
              <h2>Inventory</h2>
              <p className="help-text">Track your product stock levels and costs</p>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Quantity</th>
                    <th>Avg Cost (WAC)</th>
                    <th>Total Value</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.length > 0 ? (
                    inventory.map(item => (
                      <tr key={item.product_id}>
                        <td><strong>{item.product_name}</strong></td>
                        <td>{item.sku}</td>
                        <td className={item.quantity > 0 ? 'positive' : 'negative'}>
                          {item.quantity} units
                        </td>
                        <td>${item.wac.toFixed(2)}</td>
                        <td>${item.total_value.toLocaleString()}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>
                        No inventory yet. Purchase some products to get started!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              {inventory.length > 0 && (
                <div style={{ marginTop: '1rem', padding: '1rem', background: '#f5f5f5', borderRadius: '8px' }}>
                  <strong>Total Inventory Value: </strong>
                  ${inventory.reduce((sum, item) => sum + item.total_value, 0).toLocaleString()}
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === 'analytics' && gameState && (
          <AnalyticsDashboard companies={gameState.companies} products={products} />
        )}

        {activeTab === 'reports' && (
          <div className="dashboard">
            <section className="panel">
              <h2>Key Metrics</h2>
              {metrics && (
                <div className="metrics-grid">
                  <div className="metric">
                    <div className="metric-label">Cash Balance</div>
                    <div className="metric-value">${metrics.cash_balance.toLocaleString()}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Net Worth</div>
                    <div className="metric-value">${metrics.net_worth.toLocaleString()}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Profit Margin</div>
                    <div className="metric-value">{metrics.profit_margin.toFixed(1)}%</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">ROI</div>
                    <div className="metric-value">{metrics.roi.toFixed(1)}%</div>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="dashboard">
            <section className="panel">
              <h2>Game Logs</h2>
              <p className="help-text">Detailed turn processing logs</p>
              {logs.length > 0 ? (
                <div className="logs-container">
                  {logs.map((log, index) => (
                    <div key={index} className="log-entry">
                      <h3>Month {log.month}, Year {log.year}</h3>
                      <div className="log-content">
                        {log.lines.map((line, i) => (
                          <div key={i} className="log-line">{line}</div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#888' }}>
                  No logs yet. Advance a turn to see game processing details.
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === 'market' && (
          <MarketIntelligence />
        )}
      </main>

      {/* Decision Event Modal */}
      {pendingEvents.length > 0 && (
        <EventDecisionModal
          event={pendingEvents[0]}
          onDecide={async (choiceId) => await makeDecision(pendingEvents[0].id, choiceId)}
          onClose={() => setPendingEvents(prev => prev.slice(1))}
        />
      )}
    </div>
  )
}

export default App
