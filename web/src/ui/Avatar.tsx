/**
 * Avatar - a doctor or a staff member, as a photo or as initials.
 *
 * Initials are the normal case, not the fallback: most facility staff will
 * never upload a photo, and a grey silhouette repeated down a list carries no
 * information at all.
 */

export type AvatarSize = "sm" | "md" | "lg"

export type AvatarProps = {
  /** Full name. Initials are derived from it, and it is the image's alt text. */
  name: string
  src?: string | null
  size?: AvatarSize
  className?: string
}

const SIZE: Record<AvatarSize, string> = {
  sm: "h-8 w-8 text-label",
  md: "h-11 w-11 text-body",
  lg: "h-14 w-14 text-h3",
}

/**
 * First and last initial. Rwandan names are commonly two parts with the family
 * name first, so taking the first letter of the first and last words works in
 * both orders - and a single-word name yields one letter rather than crashing.
 */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase()
  return (
    parts[0].charAt(0) + parts[parts.length - 1].charAt(0)
  ).toUpperCase()
}

export function Avatar({ name, src, size = "md", className }: AvatarProps) {
  const shell = [
    "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full",
    SIZE[size],
    className,
  ]
    .filter(Boolean)
    .join(" ")

  if (src) {
    return <img src={src} alt={name} className={shell} />
  }

  return (
    <span
      className={`${shell} bg-primary-light font-medium text-primary`}
      // The initials are decoration over a name the surrounding row already
      // shows; announcing "MU" would only add noise.
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}

export default Avatar
