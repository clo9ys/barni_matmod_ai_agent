import React, { useState } from 'react';
import TraceLog from './TraceLog';

export default function Chat({ logs }) {
    return (
        <div className="flex-1 flex flex-col min-h-0 bg-slate-800 overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 font-mono text-sm border-b border-slate-700">
                <TraceLog logs={logs} />
            </div>
        </div>
    );
}