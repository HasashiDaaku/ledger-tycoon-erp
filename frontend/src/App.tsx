import { useState, useEffect } from 'react'
import './App.css'
import { AnalyticsDashboard } from './AnalyticsDashboard'

const API_URL = 'http://localhost:8000'

interface Company {
  id: number
  name: string
  is_player: boolean
}

interface GameState {
  current_month: number
  current_year: number
  cash_balance: number
  companies: Company[]
}

interface Account {
  id: number
  name: string
  code: string
  type: string
  balance: number
}

interface Product {
  id: number
  name: string
  sku: string
  base_cost: number
  base_price: number
  your_price: number
  units_sold: number
  revenue: number
}

interface FinancialMetrics {
  cash_balance: number
  net_worth: number
  profit_margin: number
  roi: number
  debt_ratio: number
}

interface InventoryItem {
  product_id: number
  product_name: string
  sku: string
  quantity: number
  wac: number
  total_value: number
}

function App() {
  const [gameStarted, setGameStarted] = useState(false)
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [metrics, setMetrics] = useState<FinancialMetrics | null>(null)
  const [logs, setLogs] = useState<{ month: number, year: number, lines: string[] }[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'pricing' | 'inventory' | 'reports' | 'logs' | 'analytics'>('dashboard')

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
      const response = await fetch(`${API_URL}/ledger/accounts`)
      const data = await response.json()
      setAccounts(data)
    } catch (error) {
      console.error('Error loading accounts:', error)
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
      const data = await response.json()
      setMetrics(data)
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

            <section className="panel">
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

            <section className="panel accounts-panel">
              <h2>Chart of Accounts</h2>
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Account</th>
                    <th>Type</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map(account => (
                    <tr key={account.id}>
                      <td>{account.code}</td>
                      <td>{account.name}</td>
                      <td><span className={`badge badge-${account.type.toLowerCase()}`}>{account.type}</span></td>
                      <td className={account.balance >= 0 ? 'positive' : 'negative'}>
                        ${Math.abs(account.balance).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
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
      </main>
    </div>
  )
}

export default App
