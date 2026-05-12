<!-- converted from hypothesis_definitions.xlsx -->

## Sheet: Hypothesis Definitions
| Hypothesis Type | Factor ID | Factor Name | Description/Meaning | Guidance |
| --- | --- | --- | --- | --- |
| H1: Hook Structure | question_lead | Question Lead | Headline starts with a question (e.g., 'Struggling with weight?') | Open with a plain question the buyer would actually ask. Keep it specific, not clever. |
| H1: Hook Structure | proof_lead | Proof Lead | Headline opens with credibility/numbers (e.g., 'Doctor-recommended...') | Open with proof, authority, or a concrete result window before explaining the product reason elsewhere. |
| H1: Hook Structure | contrast_loop | Contrast Loop | Uses before/after tension (e.g., 'From 90kg to 65kg...') | Open with a natural spoken contrast using but, yet, still, without, before/after, or even with. Show the old friction and the improved weight-loss path in one readable line. Avoid stiff grammar like a slogan template. |
| H1: Hook Structure | confession_lead | Confession Lead | First-person admission (e.g., 'I was ashamed of my weight...') | Open like a believable first-person admission, not a polished testimonial headline. |
| H1: Hook Structure | command_lead | Command Lead | Direct instruction (e.g., 'Stop cravings now') | Open with a direct, simple instruction only when it sounds like ad copy, not a how-to manual. |
| H2: Concept Angle | pain_point | Pain Point | Lead with the problem (e.g., 'Tired of failed diets?') | Lead from one real buyer frustration. Keep it concrete and specific, not dramatic or shame-based. |
| H2: Concept Angle | desired_outcome | Desired Outcome | Lead with the result (e.g., 'Lose 5kg in 15 days') | Lead with the practical weight-loss outcome or felt relief. Keep it believable, not transformational hype. |
| H2: Concept Angle | social_proof | Social Proof | Lead with trust (e.g., '70,000 users trusted us') | Use user count, testimonials, reviews, or served-users proof where safe. Make it specific. |
| H2: Concept Angle | authority | Authority | Lead with expertise (e.g., 'Ayurveda doctors recommend...') | Lead with doctor-formulated, Ayurveda, or expert credibility. Keep it simple and ad-readable. |
| H2: Concept Angle | curiosity | Curiosity | Lead with mystery (e.g., 'The secret doctors don't tell...') | Lead with a specific mechanism gap or question that makes the reader want the explanation. Avoid clickbait. |
| H2: Concept Angle | comparison | Comparison | Contrast with harder alternatives (e.g., 'No gym. No starving.') | Lead by contrasting the kit with strict diets, random attempts, or high-friction routines. Avoid competitor bashing. |
| H2: Concept Angle | offer | Offer | Lead with practical reason to act (e.g., 'Get free shipping') | Lead with a clear reason to act: 15-day result window, kit completeness, or guarantee logic. Do not mention price. |
| H3: Awareness Stage | unaware | Unaware | Reader doesn't know they have a weight problem | Name a hidden daily friction before talking like the reader already wants this kit. |
| H3: Awareness Stage | problem_aware | Problem Aware | Reader knows they have a problem but not the solution | Start from a problem the reader already recognizes, then make the next step feel clear. |
| H3: Awareness Stage | solution_aware | Solution Aware | Reader knows solutions exist but not why this one | Assume the reader has tried fixes. Show why this system is easier, safer, or more guided. |
| H3: Awareness Stage | product_aware | Product Aware | Reader already knows the product, just needs a push | Assume the reader knows the kit. Give a proof, urgency, trust, or simplicity push to act. |
| H4: Proof Style | authority_anchor | Authority Anchor | Doctor credibility, Ayurveda trust | Use doctor-formulated or Ayurvedic credibility as the trust lane. Avoid vague 'expert-backed' filler. |
| H4: Proof Style | social_proof | Social Proof | User testimonials, '70,000+ users' | Use user count, testimonials, reviews, or served-users proof where safe. Make it specific. |
| H4: Proof Style | mechanism_explainer | Mechanism Explainer | Step-by-step how it works | Explain the product mechanism simply: hunger/cravings, routine, fullness, digestion, or adherence. |
| H4: Proof Style | routine_clarity | Routine Clarity | Simple daily steps | Make the proof feel easy to follow: clear steps, low guesswork, simple daily routine. |
| H4: Proof Style | objection_flip | Objection Flip | Address skepticism directly | Address a real doubt directly, then resolve it with proof or mechanism. Avoid sounding defensive. |
| H5: CTA Voice | urgent_start | Urgent Start | 'Start Today', 'Act Now' | Ask for action now/today without sounding pushy or using sale pressure. |
| H5: CTA Voice | guided_next_step | Guided Next Step | 'See The Steps', 'View Details' | Ask the user to see, check, or view the plan/protocol/steps. |
| H5: CTA Voice | reassurance_start | Reassurance Start | 'Check If It Fits', 'Try Risk-Free' | Make the next step feel safe or low-risk: check fit, see if it suits, try safely. |
| H5: CTA Voice | challenge_action | Challenge Action | 'Take The 15-Day Test' | Frame the action as a 15-day test or challenge. Keep it compliant and simple. |
| H5: CTA Voice | discovery_action | Discovery Action | 'See How It Works', 'Learn More' | Invite learning: see how it works, learn the steps, discover the routine. |
| H6: Concept Structure | pas | PAS | Problem → Agitation → Solution | Shape copy as problem first, consequence next, then product-led resolution. |
| H6: Concept Structure | bab | BAB | Before → After → Bridge | Use before-to-after bridge flow: current struggle, better state, then the bridge routine. |
| H6: Concept Structure | fab | FAB | Feature → Advantage → Benefit | Lead with concrete feature, explain practical advantage, then connect to weight-loss benefit. |
| H6: Concept Structure | four_us | Four Us | Useful, Urgent, Unique, Ultra-specific | Keep wording useful, honestly urgent, unique enough to stand out, and ultra-specific. |
## Sheet: Default Values
| Hypothesis Type | Field Type | Required? | Default Value | How Value is Determined |
| --- | --- | --- | --- | --- |
| H1: Hook Structure | Hypothesis Only | No | not_set | Only used when testing this hypothesis |
| H2: Concept Angle | Required + Hypothesis | Yes | desired_outcome | varies by feature (see feature mapping below) |
| H3: Awareness Stage | Required + Hypothesis | Yes | problem_aware | hardcoded default |
| H4: Proof Style | Hypothesis Only | No | not_set | Only used when testing this hypothesis |
| H5: CTA Voice | Hypothesis Only | No | not_set | Only used when testing this hypothesis |
| H6: Concept Structure | Required + Hypothesis | Yes | four_us | varies by format (see format mapping below) |
| FEATURE-BASED CONCEPT ANGLE (H2) - applies when NO hypothesis selected |  |  |  |  |
| When you advertise this feature... | ...use this concept_angle (messaging angle) |  |  |  |
| am_routine (morning routine) | curiosity → Lead with question or mechanism gap |  |  |  |
| pm_routine (evening routine) | story → Lead with real-life routine narrative |  |  |  |
| cravings_down (hunger/cravings control) | pain_point → Lead with specific problem/friction |  |  |  |
| guided_support (support/community) | social_proof → Lead with trust and testimonials |  |  |  |
| structured_system (the system) | desired_outcome → Lead with result or felt outcome |  |  |  |
| homemade_food (food aspect) | comparison → Contrast with stricter/harder alternatives |  |  |  |
| natural_safe (natural/ayurveda) | authority → Lead with doctor/Ayurveda credibility |  |  |  |
| proof_guarantee (results/guarantee) | offer → Lead with practical reason to act |  |  |  |
| FORMAT-BASED CONCEPT STRUCTURE (H6) - applies when NO hypothesis selected |  |  |  |  |
| When you generate this format... | ...use this concept_structure (copy flow) |  |  |  |
| HERO (hero image) | four_us → Useful, urgent, unique, ultra-specific |  |  |  |
| BA (before/after) | bab → Before → After → Bridge |  |  |  |
| TEST (testimonial) | bab → Before → After → Bridge |  |  |  |
| FEAT (features) | fab → Feature → Advantage → Benefit |  |  |  |
| UGC (creator style) | pas → Problem → Agitation → Solution |  |  |  |
| IMPORTANT: Hypothesis only affects the ONE dimension you select |  |  |  |  |
| Example: Selecting concept_angle=offer ONLY changes concept_angle |  |  |  |  |
| - awareness_stage stays at default: problem_aware |  |  |  |  |
| - concept_structure stays at format rotation logic |  |  |  |  |