# Ledger Tycoon - Business Simulation Game

A realistic business simulation game where you manage accounting, logistics, and inventory while competing against AI bot companies. The game progresses month-by-month, simulating a realistic market economy with double-entry accounting.

## 🎮 Features

- **Double-Entry Accounting**: Full ledger system with automatic bookkeeping
- **Inventory Management**: Track products, warehouses, and stock levels
- **Market Competition**: Compete against AI-controlled bot companies
- **Monthly Turns**: Strategic turn-based gameplay
- **Financial Reports**: Real-time balance sheet and account tracking

## 🏗️ Project Structure

```
accounting_erp_software/
├── backend/          # Python FastAPI backend
│   ├── app/
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── models.py        # SQLAlchemy database models
│   │   ├── schemas.py       # Pydantic validation schemas
│   │   ├── database.py      # Database configuration
│   │   └── routers/         # API endpoints
│   │       ├── ledger.py    # Accounting endpoints
│   │       └── simulation.py # Game logic endpoints
│   └── core/
│       ├── accounting.py    # Double-entry accounting logic
│       └── engine.py        # Game engine & turn processing
│
└── frontend/         # React TypeScript frontend
    └── src/
        ├── App.tsx          # Main app component
        └── App.css          # Styling
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Installation

1. **Clone the repository** (if using git)

2. **Setup Backend:**

```bash
cd backend

# Activate virtual environment (if created)
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python -m uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

3. **Setup Frontend:**

```bash
cd frontend

# Install dependencies (if not already done)
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

## 🎯 How to Play

1. **Start the Game**: Click "Start New Game" to initialize your company with $100,000 capital
2. **View Your Finances**: Check the Chart of Accounts panel to see your financial position
3. **Make Decisions**: 
   - Purchase inventory to stock your warehouse
   - Set prices for your products
   - Manage cash flow
4. **Advance Time**: Click "Next Month" to process a turn
   - Warehouse rent is automatically deducted
   - Sales are calculated based on market demand
   - Bot competitors make their moves
5. **Compete**: Monitor competitor companies and adjust your strategy

## 📊 Game Mechanics

### Accounting System
- **Assets**: Cash, Inventory, Accounts Receivable, Warehouses
- **Liabilities**: Accounts Payable, Loans
- **Equity**: Owner's Capital, Retained Earnings
- **Revenue**: Sales
- **Expenses**: COGS, Rent, Marketing, Logistics

Every business transaction automatically creates balanced journal entries.

### Turn Processing
Each month:
1. Warehouse costs are deducted
2. Market demand is calculated
3. Sales are processed
4. Bot AI makes decisions
5. Financial statements are updated

### Bot Competition
AI-controlled companies:
- Analyze their P&L and market share
- Adjust pricing strategies
- Make inventory purchases
- Compete for market share

## 🛠️ Tech Stack

**Backend:**
- FastAPI - Modern Python web framework
- SQLAlchemy - ORM for database operations
- SQLite - Database (async with aiosqlite)
- Pydantic - Data validation

**Frontend:**
- React 18
- TypeScript
- Vite - Build tool
- CSS3 with modern gradients

## 📝 API Endpoints

### Game Endpoints (`/game`)
- `POST /game/start` - Initialize new game
- `GET /game/state` - Get current game state
- `POST /game/turn` - Advance one month
- `POST /game/purchase` - Purchase inventory

### Ledger Endpoints (`/ledger`)
- `GET /ledger/accounts` - View all accounts with balances
- `GET /ledger/transactions` - View transaction history

## 🔮 Future Enhancements

- [ ] Advanced demand simulation with seasonality
- [ ] Multiple products with different market segments
- [ ] Marketing campaigns
- [ ] Detailed sales analytics
- [ ] Supply chain management
- [ ] Bank loans and financing
- [ ] Multiplayer support
- [ ] Win conditions and achievements

## 📄 License

This project is for educational/demonstration purposes.

---

**Built with ❤️ using FastAPI and React**
