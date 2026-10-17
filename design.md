# Entitle design system

The citizen and reviewer views share one calm, practical visual language. Teal marks actions and verified support; quotations and review decisions remain easy to distinguish.

## Genre and structure

- Genre: modern-minimal with an editorial display face.
- Marketing and citizen pages: compact introduction followed by a clear profile or matches task.
- Reviewer pages: workbench layout with the source, evidence, and decision kept together.
- Existing routes, page hierarchy, and product copy remain owned by the application templates.

## Theme

Use the named values in `app/static/tokens.css`. The palette pairs a pale green-grey page with deep green ink and a restrained teal accent. Teal is reserved for navigation, primary actions, and verified steps.

## Typography

- Display: Bricolage Grotesque, upright, for headings and the Entitle wordmark.
- Body: Public Sans for labels, instructions, and longer text.
- Mono: IBM Plex Mono for source receipts and technical details.

## Motion and interaction

- Use a gentle fade and short upward movement as content enters the viewport.
- Animate the four-step trust timeline in sequence.
- Honor `prefers-reduced-motion` and keep all content visible without JavaScript.
- Keep buttons pill shaped, provide visible keyboard focus, and use native dialog behavior for admin sign-in.

## Shared app elements

- Use the same SVG mark in the header and favicon.
- Keep the centered oval navigation, teal action color, display and body fonts, and rounded control shapes consistent across the citizen and reviewer views.
- Keep source quotes, human approvals, pending changes, and blocked rules visually distinct.
