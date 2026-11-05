// Players changing the photo on their own card: staff approve each one first.

import type { PlayerCard } from "./cards";

export type PhotoRequestStatus = "PENDING" | "APPROVED" | "REJECTED" | "WITHDRAWN";

export type PhotoRequest = {
  id: number;
  status: PhotoRequestStatus;
  /** The picture sent (private: only the player and staff can open it); gone once dealt with. */
  image: string | null;
  reason: string;
  created_at: string;
  reviewed_at: string | null;
};

export type StaffPhotoRequest = PhotoRequest & {
  player: { id: number; name: string; game_uid: string; team: string | null; photo: string | null };
  requested_by: string | null;
  reviewed_by: string | null;
};

export type MyCard = {
  player: {
    id: number;
    name: string;
    game_uid: string;
    team: { name: string; tag: string } | null;
    photo: string | null;
    card_hidden: boolean;
  } | null;
  pending_uid_claim?: string | null;
  card?: PlayerCard | null;
  request?: PhotoRequest | null;
};

/** One line telling the player where their latest photo request stands (null: nothing to say). */
export function requestLine(req: PhotoRequest | null | undefined): string | null {
  if (!req) return null;
  switch (req.status) {
    case "PENDING":
      return "Your new photo is waiting for league staff to approve it. Your card keeps its current photo until then.";
    case "APPROVED":
      return "Your new photo was approved and is on your card.";
    case "REJECTED":
      return req.reason
        ? `League staff didn't approve your last photo: ${req.reason}`
        : "League staff didn't approve your last photo. You can send another one.";
    default:
      return null;
  }
}

/** Biggest photo the server takes. */
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** Checks a picture before sending it; returns what's wrong, or null when it's fine. */
export function photoProblem(file: { size: number; type: string }): string | null {
  if (!PHOTO_TYPES.includes(file.type)) return "Use a JPEG, PNG or WebP picture.";
  if (file.size > PHOTO_MAX_BYTES) return "Photos can be at most 5 MB.";
  return null;
}
