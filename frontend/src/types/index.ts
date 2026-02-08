export interface Company {
    id: number;
    name: string;
    is_player: boolean;
    cash?: number;
    brand_equity?: number;
    strategy_memory?: {
        stockouts?: Record<string, number>;
        pricing_regret?: Record<string, number>;
        inventory_waste?: Record<string, number>;
        adaptations?: any[];
    };
    personality?: string;
}

export interface GameState {
    current_month: number;
    current_year: number;
    cash_balance: number;
    companies: Company[];
}

export interface Account {
    id: number;
    name: string;
    code: string;
    type: string;
    balance: number;
}

export interface Product {
    id: number;
    name: string;
    sku: string;
    base_cost: number;
    base_price: number;
    your_price: number;
    units_sold: number;
    revenue: number;
}

export interface FinancialMetrics {
    cash_balance: number;
    net_worth: number;
    profit_margin: number;
    roi: number;
    debt_ratio: number;
}

export interface InventoryItem {
    product_id: number;
    product_name: string;
    sku: string;
    quantity: number;
    wac: number;
    total_value: number;
}

export interface LogEntry {
    month: number;
    year: number;
    lines: string[];
}
