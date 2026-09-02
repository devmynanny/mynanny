"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { AdminPermanentPlacements } from "@/components/permanent-placement/admin";
import { NannyPermanentPlacements } from "@/components/permanent-placement/nanny";
import { ParentPermanentPlacements } from "@/components/permanent-placement/parent";

export default function PermanentPlacementsPage() {
  return (
    <AuthenticatedPage returnTo="/placements">
      {(role) =>
        role === "admin" ? (
          <AdminPermanentPlacements />
        ) : role === "nanny" ? (
          <NannyPermanentPlacements />
        ) : (
          <ParentPermanentPlacements />
        )
      }
    </AuthenticatedPage>
  );
}
