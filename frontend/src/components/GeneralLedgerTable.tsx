
import React, { useEffect, useState } from 'react';

interface Account {
    id: number;
    code: string;
    name: string;
    type: string;
    balance: number;
}

interface GeneralLedgerTableProps {
    accounts: Account[];
}

export const GeneralLedgerTable: React.FC<GeneralLedgerTableProps> = ({ accounts }) => {
    return (
        <div className="panel general-ledger-panel">
            <h2>General Ledger (Trial Balance)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Account</th>
                        <th>Type</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Net Balance</th>
                    </tr>
                </thead>
                <tbody>
                    {accounts.map(account => {
                        const isDebitNormal = ['Asset', 'Expense'].includes(account.type);
                        const balance = account.balance;
                        let debit = 0;
                        let credit = 0;

                        // Simplified display logic: 
                        // Assets/Expenses: Positive balance is Debit.
                        // Liabilities/Equity/Revenue: Positive balance (in DB) is usually Credit.
                        // However, DB storage convention matters. 
                        // Assuming standard DB storage where Asset+ and Liability-
                        // Let's rely on the displayed balance for now, but split columns for GL view.

                        if (balance >= 0) {
                            if (isDebitNormal) debit = balance;
                            else credit = balance; // Should be impossible if strictly following normal balance?
                            // Actually, let's just show absolute value in the correct column based on sign
                        }

                        // Better approach for Trial Balance:
                        // If we don't have raw debit/credit sums, we just map balance to column.
                        const absBalance = Math.abs(balance);
                        if (balance >= 0) {
                            // Positive number. 
                            // If Asset/Expense, it's a Debit balance.
                            // If Liability/Equity/Revenue, it's a Credit balance?
                            // Wait, usually Revenue is Credit, Expense is Debit.
                            // Let's assume standard accounting sign convention in the DB:
                            // Assets/Expenses > 0
                            // Liabilities/Equity/Revenue < 0? 
                            // OR everything is positive and Type dictates side?
                            // Looking at App.tsx: 
                            // <td className={account.balance >= 0 ? 'positive' : 'negative'}>
                            // It seems to just show raw number.

                            // Let's implement standard "Normal Balance" logic for columns
                            if (isDebitNormal) {
                                debit = balance;
                            } else {
                                // If it's Liability and balance is positive, does that mean we have debt (Credit)?
                                // Let's assume positive means "Normal Balance" for that type.
                                credit = balance;
                                // If the DB stores everything as positive for "increase", then:
                                // Assets: + is Debit
                                // Liabilities: + is Credit
                            }
                        } else {
                            // Negative balance (Contra account or overdraft)
                            if (isDebitNormal) {
                                credit = Math.abs(balance);
                            } else {
                                debit = Math.abs(balance);
                            }
                        }

                        return (
                            <tr key={account.id}>
                                <td>{account.code}</td>
                                <td>{account.name}</td>
                                <td><span className={`badge badge-${account.type.toLowerCase()}`}>{account.type}</span></td>
                                <td>{debit !== 0 ? `$${debit.toLocaleString()}` : '-'}</td>
                                <td>{credit !== 0 ? `$${credit.toLocaleString()}` : '-'}</td>
                                <td className={account.balance >= 0 ? 'positive' : 'negative'}>
                                    ${Math.abs(account.balance).toLocaleString()}
                                </td>
                            </tr>
                        );
                    })}
                    <tr className="total-row" style={{ fontWeight: 'bold', borderTop: '2px solid #ccc' }}>
                        <td colSpan={3} style={{ textAlign: 'right' }}>Totals:</td>
                        {/* Calculating totals would be good validation */}
                        <td>
                            ${accounts.reduce((sum, a) => {
                                return ['Asset', 'Expense'].includes(a.type) ? sum + a.balance : sum;
                            }, 0).toLocaleString()}
                        </td>
                        <td>
                            ${accounts.reduce((sum, a) => {
                                return ['Liability', 'Equity', 'Revenue'].includes(a.type) ? sum + a.balance : sum;
                            }, 0).toLocaleString()}
                        </td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};
