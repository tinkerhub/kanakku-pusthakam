import type { Key } from "react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { DataTable, DetailDrawer, FilterBar, StatusBadge } from "../../../components/ui";
import type { DataTableColumn } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { categoryResults, Panel, type CategoryListResponse, type Makerspace, type Product, useStaffGet } from "./shared";

export function Inventory({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const storageKey = `inventory.view.${makerspace.id}`;
  const [search, setSearch] = useState(() => localStorage.getItem(storageKey) ?? "");
  const [selectedIds, setSelectedIds] = useState<Key[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const products = useStaffGet<{ results: Product[] }>(
    ["inventory", makerspace.id],
    `/admin/makerspace/${makerspace.id}/inventory`,
  );
  const categories = useStaffGet<CategoryListResponse>(
    ["categories", makerspace.id],
    `/admin/makerspace/${makerspace.id}/categories`,
  );
  const toggle = useMutation({
    mutationFn: (product: Product) =>
      staffRequest(`/admin/inventory/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          public_self_checkout_enabled: !product.public_self_checkout_enabled,
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory", makerspace.id] }),
  });
  const updateCategory = useMutation({
    mutationFn: ({ product, category }: { product: Product; category: number | null }) =>
      staffRequest(`/admin/inventory/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ category }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["categories", makerspace.id] });
    },
  });
  const bulkQr = useMutation({
    mutationFn: (enabled: boolean) =>
      Promise.all(
        selectedIds.map((id) =>
          staffRequest(`/admin/inventory/${String(id)}`, {
            method: "PATCH",
            body: JSON.stringify({ public_self_checkout_enabled: enabled }),
          }),
        ),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory", makerspace.id] }),
  });
  const allProducts = products.data?.results ?? [];
  const rows = allProducts.filter((product) =>
    [product.name, product.description, product.tracking_mode]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const selectedCount = selectedIds.length;
  const drawerProduct = selectedProduct ? allProducts.find((product) => product.id === selectedProduct.id) ?? selectedProduct : null;
  const categoryRows = categoryResults(categories.data);
  const columns: DataTableColumn<Product>[] = [
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (product) => (
        <button
          type="button"
          className="text-left font-semibold text-ink hover:text-accent"
          onClick={() => setSelectedProduct(product)}
        >
          {product.name}
        </button>
      ),
    },
    { key: "tracking_mode", header: "Mode", sortable: true },
    { key: "total_quantity", header: "Total", sortable: true },
    {
      key: "available_quantity",
      header: "Available",
      sortable: true,
      render: (product) => <InventoryAvailability product={product} />,
    },
    { key: "issued_quantity", header: "Issued", sortable: true },
    { key: "damaged_quantity", header: "Damaged", sortable: true },
    { key: "lost_quantity", header: "Lost", sortable: true },
    {
      key: "public_self_checkout_enabled",
      header: "Public QR",
      render: (product) => (
        <button className="desk-button" type="button" onClick={() => toggle.mutate(product)}>
          {product.public_self_checkout_enabled ? "Allowed" : "Off"}
        </button>
      ),
    },
  ];
  return (
    <Panel title="Inventory">
      <div className="grid gap-3">
        <FilterBar
          value={search}
          onChange={setSearch}
          placeholder="Filter table"
          actions={(
            <>
              <button
                className="desk-button"
                type="button"
                onClick={() => {
                  localStorage.setItem(storageKey, search);
                }}
              >
                Save view
              </button>
              <button className="desk-button" type="button" disabled={!selectedCount || bulkQr.isPending} onClick={() => bulkQr.mutate(true)}>
                Enable QR
              </button>
              <button className="desk-button" type="button" disabled={!selectedCount || bulkQr.isPending} onClick={() => bulkQr.mutate(false)}>
                Disable QR
              </button>
            </>
          )}
        />
        <DataTable<Product>
          columns={columns}
          data={rows}
          getRowId={(row) => row.id}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          loading={products.isLoading}
          emptyTitle="No inventory"
        />
      </div>
      <DetailDrawer
        open={Boolean(drawerProduct)}
        title={drawerProduct?.name ?? "Inventory item"}
        onClose={() => setSelectedProduct(null)}
      >
        {drawerProduct ? (
          <div className="grid gap-4 text-sm">
            <div className="grid gap-2 sm:grid-cols-2">
              <InventoryMetric label="Total" value={drawerProduct.total_quantity} />
              <InventoryMetric label="Available" value={drawerProduct.available_quantity} />
              <InventoryMetric label="Issued" value={drawerProduct.issued_quantity} />
              <InventoryMetric label="Damaged" value={drawerProduct.damaged_quantity} />
              <InventoryMetric label="Lost" value={drawerProduct.lost_quantity} />
            </div>
            <dl className="grid gap-2 text-muted">
              <div className="flex justify-between gap-3">
                <dt>Tracking mode</dt>
                <dd className="font-medium text-ink">{drawerProduct.tracking_mode}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Public</dt>
                <dd className="font-medium text-ink">{drawerProduct.is_public ? "yes" : "no"}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>Category</dt>
                <dd>
                  <select
                    className="desk-input"
                    value={drawerProduct.category ?? ""}
                    disabled={categories.isLoading || updateCategory.isPending}
                    onChange={(event) =>
                      updateCategory.mutate({
                        product: drawerProduct,
                        category: event.target.value ? Number(event.target.value) : null,
                      })
                    }
                  >
                    <option value="">Uncategorized</option>
                    {categoryRows.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>Public self-checkout</dt>
                <dd>
                  <button className="desk-button" type="button" onClick={() => toggle.mutate(drawerProduct)}>
                    {drawerProduct.public_self_checkout_enabled ? "Allowed" : "Off"}
                  </button>
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Box id</dt>
                <dd className="font-medium text-ink">{drawerProduct.box ?? "none"}</dd>
              </div>
            </dl>
            {updateCategory.error ? <p className="text-sm text-danger">{updateCategory.error.message}</p> : null}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Description</h3>
              <p className="mt-2 text-muted">{drawerProduct.description || "No description."}</p>
            </div>
          </div>
        ) : null}
      </DetailDrawer>
    </Panel>
  );
}


function InventoryAvailability({ product }: { product: Product }) {
  const badge =
    product.available_quantity <= 0 ? (
      <StatusBadge status="lost" label="Unavailable" />
    ) : product.available_quantity <= Math.ceil(product.total_quantity * 0.2) ? (
      <StatusBadge status="limited" label="Limited" />
    ) : (
      <StatusBadge status="available" label="Available" />
    );
  // Keep the exact count visible alongside the status band — staff make stock
  // decisions on the number, not just the band.
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-medium text-ink">{product.available_quantity}</span>
      {badge}
    </span>
  );
}

function InventoryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-line bg-surface p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-bold text-ink">{value}</p>
    </div>
  );
}
