/**
 * Avatar - a doctor or a staff member, as a photo or as initials.
 *
 *  Initials are the normal case, not the fallback: most facility staff will
 *  never upload a photo, and a grey silhouette repeated down a list carries no
 *  information at all.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

export type AvatarSize = "sm" | "md" | "lg"

export type AvatarProps = {
  /** Full name. Initials are derived from it, and it is the alt text. */
  name: string
  src?: string | null
  size?: AvatarSize
  className?: string
}

export function Avatar(_props: AvatarProps) {
  return null
}

export default Avatar
