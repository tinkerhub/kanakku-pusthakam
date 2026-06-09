import { Card } from "../../components/ui/Card";
import type { Product } from "../../types/inventory";
import { AvailabilityBadge } from "./AvailabilityBadge";

type ProductCardProps = {
  product: Product;
};

export function ProductCard({ product }: ProductCardProps) {
  return (
    <Card className="flex h-full flex-col gap-4">
      <div className="flex flex-1 flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-semibold leading-6 text-ink">
            {product.name}
          </h2>
          <AvailabilityBadge availability={product.availability} />
        </div>
        <p className="line-clamp-2 text-sm leading-6 text-ink/70">
          {product.description}
        </p>
      </div>
    </Card>
  );
}
