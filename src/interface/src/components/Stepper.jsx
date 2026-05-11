import React from 'react';

export default function Stepper({ steps, current, selected, onSelect }) {
    return (
        <ul className="flex items-center gap-1 w-full overflow-x-auto no-scrollbar">
            {steps.map((step, index) => {
                const isActive = index === selected;
                const isCompleted = index <= current;
                
                return (
                    <li
                        key={index}
                        className={`
                            flex items-center gap-2 px-4 py-2 cursor-pointer whitespace-nowrap transition-all rounded-lg
                            ${isActive ? 'bg-soft-accent/10 text-soft-accent font-bold' : 'text-soft-muted hover:text-soft-text'}
                            ${!isCompleted && 'opacity-40 cursor-not-allowed'}
                        `}
                        onClick={() => isCompleted && onSelect(index)}
                    >
                        <span className={`
                            w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold border
                            ${isActive ? 'bg-soft-accent text-white border-soft-accent' : 'border-soft-muted'}
                        `}>
                            {index + 1}
                        </span>
                        <span className="text-sm tracking-tight">{step}</span>
                        {index < steps.length - 1 && (
                            <span className="ml-2 text-soft-border">/</span>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}