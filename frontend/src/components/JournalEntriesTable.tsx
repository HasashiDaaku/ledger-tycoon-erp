
import React, { useEffect, useState } from 'react';

interface JournalEntry {
    id: number;
    account: {
        code: string;
        name: string;
    };
    debit: number;
    credit: number;
    description: string;
}

interface Transaction {
    id: number;
    date: string;
    description: string;
    journal_entries: JournalEntry[];
}

interface JournalEntriesTableProps {
    companyId: number;
}

export const JournalEntriesTable: React.FC<JournalEntriesTableProps> = ({ companyId }) => {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (companyId) {
            fetchTransactions();
        }
    }, [companyId]);

    const fetchTransactions = async () => {
        setLoading(true);
        try {
            const response = await fetch(`http://localhost:8000/ledger/journal-entries/${companyId}`);
            const data = await response.json();
            setTransactions(data);
        } catch (error) {
            console.error("Failed to fetch journal entries", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="panel journal-entries-panel">
            <h2>Journal Entries</h2>
            <button onClick={fetchTransactions} disabled={loading} style={{ marginBottom: '1rem' }}>
                🔄 Refresh
            </button>

            {loading ? (
                <p>Loading entries...</p>
            ) : (
                <table className="journal-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Description</th>
                            <th>Account</th>
                            <th>Debit</th>
                            <th>Credit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {transactions.map(tx => (
                            <React.Fragment key={tx.id}>
                                {tx.journal_entries.map((entry, index) => (
                                    <tr key={entry.id} className={index === 0 ? "transaction-start" : ""}>
                                        <td>{index === 0 ? new Date(tx.date).toLocaleDateString() : ''}</td>
                                        <td>{index === 0 ? tx.description : ''}</td>
                                        <td>{entry.account.code} - {entry.account.name}</td>
                                        <td className={entry.debit > 0 ? "debit-cell" : ""}>
                                            {entry.debit > 0 ? `$${entry.debit.toLocaleString()}` : ''}
                                        </td>
                                        <td className={entry.credit > 0 ? "credit-cell" : ""}>
                                            {entry.credit > 0 ? `$${entry.credit.toLocaleString()}` : ''}
                                        </td>
                                    </tr>
                                ))}
                                <tr className="spacer-row"><td colSpan={5} style={{ height: '10px', background: '#f9f9f9' }}></td></tr>
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};
