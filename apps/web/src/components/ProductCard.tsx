import React from 'react';
import { Product } from '../types/chat';

interface Props {
  product: Product;
}

export const ProductCard: React.FC<Props> = ({ product }) => {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 shadow-md text-slate-100 flex flex-col justify-between my-2">
      <div>
        <div className="flex justify-between items-start mb-2">
          <h4 className="font-semibold text-base text-white">{product.name}</h4>
          <span className="bg-indigo-900 text-indigo-200 text-xs px-2 py-0.5 rounded font-mono">
            {product.id}
          </span>
        </div>

        <p className="text-xs text-slate-400 mb-3">{product.category.toUpperCase()}</p>

        {product.dimensions && (
          <p className="text-xs text-slate-300 mb-2">
            📏 <strong>Dimensions:</strong> {product.dimensions.width}×{product.dimensions.depth}×{product.dimensions.height} cm
          </p>
        )}
      </div>

      <div className="flex justify-between items-center border-t border-slate-700 pt-3 mt-2">
        <span className="text-lg font-bold text-emerald-400">
          ${product.price.toFixed(2)}
        </span>
        <span className={`text-xs px-2 py-1 rounded ${product.stock > 0 ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-red-300'}`}>
          {product.stock > 0 ? `${product.stock} in stock` : 'Out of stock'}
        </span>
      </div>
    </div>
  );
};
