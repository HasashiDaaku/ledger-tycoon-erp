import React, { useState, useEffect } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    AreaChart, Area, BarChart, Bar
} from 'recharts';

const API_URL = 'http://localhost:8000';

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#d0ed57', '#a4de6c'];

interface AnalyticsDashboardProps {
    companies: { id: number; name: string; is_player: boolean }[];
    products: { id: number; name: string }[];
}

export function AnalyticsDashboard({ companies, products }: AnalyticsDashboardProps) {
    const [marketHistory, setMarketHistory] = useState<any[]>([]);
    const [financialHistory, setFinancialHistory] = useState<any[]>([]);
    const [selectedProduct, setSelectedProduct] = useState<number>(products[0]?.id || 1);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // Automatically select the first product if none selected or if selection is missing from products
        if (products.length > 0) {
            const currentExists = products.find(p => p.id === selectedProduct);
            if (!currentExists) {
                setSelectedProduct(products[0].id);
            }
        }
        fetchData();
    }, [selectedProduct, products, companies]);

    const fetchData = async () => {
        setLoading(true);
        try {
            // Fetch Market History
            const marketRes = await fetch(`${API_URL}/game/history/market?product_id=${selectedProduct}`);
            const marketData = await marketRes.json();
            setMarketHistory(processMarketData(marketData));

            // Fetch Financial History (Player Company)
            const player = companies.find(c => c.is_player);
            if (player) {
                const finRes = await fetch(`${API_URL}/game/history/financial?company_id=${player.id}`);
                const finData = await finRes.json();
                setFinancialHistory(processFinancialData(finData));
            }
        } catch (error) {
            console.error("Error fetching history:", error);
        } finally {
            setLoading(false);
        }
    };

    const processMarketData = (data: any[]) => {
        // Pivot data: Group by month/year -> { label: "1/2026", comp1_price: 10, comp2_price: 12 ... }
        const grouped: any = {};

        data.forEach(item => {
            const key = `${item.month}/${item.year}`;
            if (!grouped[key]) {
                grouped[key] = { name: key, month: item.month, year: item.year };
            }

            // Add price and sales for this company
            grouped[key][`price_${item.company_id}`] = item.price;
            grouped[key][`sales_${item.company_id}`] = item.units_sold;
            grouped[key][`rev_${item.company_id}`] = item.revenue;
        });

        return Object.values(grouped).sort((a: any, b: any) => {
            if (a.year !== b.year) return a.year - b.year;
            return a.month - b.month;
        });
    };

    const processFinancialData = (data: any[]) => {
        return data.map(item => ({
            name: `${item.month}/${item.year}`,
            cash: item.cash_balance,
            assets: item.total_assets,
            equity: item.total_equity
        }));
    };

    return (
        <div className="analytics-dashboard">
            <div className="controls">
                <label>Product: </label>
                <select value={selectedProduct} onChange={(e) => setSelectedProduct(Number(e.target.value))}>
                    {products.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                </select>
                <button onClick={fetchData} disabled={loading}>Refresh</button>
            </div>

            <div className="charts-container">
                {/* Price History */}
                <div className="chart-box">
                    <h3>Price Trends (Competitor Analysis)</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={marketHistory}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis label={{ value: 'Price ($)', angle: -90, position: 'insideLeft' }} />
                            <Tooltip />
                            <Legend />
                            {companies.map((company, index) => (
                                <Line
                                    key={company.id}
                                    type="monotone"
                                    dataKey={`price_${company.id}`}
                                    name={`${company.name} Price`}
                                    stroke={COLORS[index % COLORS.length]}
                                    strokeWidth={company.is_player ? 3 : 1}
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Sales Volume */}
                <div className="chart-box">
                    <h3>Sales Volume (Units Sold)</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={marketHistory}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            {companies.map((company, index) => (
                                <Bar
                                    key={company.id}
                                    dataKey={`sales_${company.id}`}
                                    name={`${company.name} Sales`}
                                    fill={COLORS[index % COLORS.length]}
                                    stackId="a"
                                />
                            ))}
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Financial Health */}
                <div className="chart-box">
                    <h3>Cash Balances (Player)</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={financialHistory}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <Area type="monotone" dataKey="cash" name="Cash Balance" stroke="#8884d8" fill="#8884d8" />
                            <Area type="monotone" dataKey="assets" name="Total Assets" stroke="#82ca9d" fill="#82ca9d" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
