# Auto-drafted runbook entries

Generated at `1779725213996` (UTC ms).  
Each section below is **a draft** assembled from oncall corrections (`verdict ∈ thumbs_down|incorrect` with `correct_root_cause` set). Review before merging.

- **40** cluster(s) ready for review
- **228** cluster(s) below the `min_occurrences=5` threshold (suppressed)

---

## `recommend-feed` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **12** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** disable feature flag svc.recommend-feed.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for payments-gateway was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream order-pipeline timeout, not recommend-feed
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** disable feature flag svc.recommend-feed.new_path

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the recommend-feed sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

_…and 2 more occurrences_

### Suggested runbook entry

> When `recommend-feed` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the recommend-feed sidecar**.
>
> Recommended first action: `disable feature flag svc.recommend-feed.new_path`

---

## `image-thumbnail` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **10** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream cdn-router timeout, not image-thumbnail

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream inventory-sync timeout, not image-thumbnail
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** disable feature flag svc.image-thumbnail.new_path

### Suggested runbook entry

> When `image-thumbnail` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `cart-service` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **10** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream notification-fanout timeout, not cart-service
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the cart-service sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** page the rate-limiter-edge oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `cart-service` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the cart-service sidecar**.
>
> Recommended first action: `increase cart-service concurrency limit to 2x and re-rate-limit upstream`

---

## `inventory-sync` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **10** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream inventory-sync timeout, not inventory-sync
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for payments-gateway was filling our partition
  **action:** page the ad-bidder oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream order-pipeline timeout, not inventory-sync
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `inventory-sync` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.inventory-sync.new_path`

---

## `search-suggest` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream comment-svc timeout, not search-suggest
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `search-suggest` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in search-suggest, not what the agent said**.
>
> Recommended first action: `increase search-suggest concurrency limit to 2x and re-rate-limit upstream`

---

## `ad-bidder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **9** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** actually a downstream session-store timeout, not ad-bidder

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cdn-router timeout, not ad-bidder

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** {svc} health-check failure cascade
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream price-cache timeout, not ad-bidder
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `ad-bidder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `inventory-sync` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **9** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream video-encoder timeout, not inventory-sync
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `inventory-sync` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `rate-limiter-edge` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in rate-limiter-edge, not what the agent said

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in rate-limiter-edge, not what the agent said
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream inventory-sync timeout, not rate-limiter-edge
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream user-profile timeout, not rate-limiter-edge

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `rate-limiter-edge` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the rate-limiter-edge sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `notification-fanout` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream user-profile timeout, not notification-fanout

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** page the comment-svc oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream comment-svc timeout, not notification-fanout
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

### Suggested runbook entry

> When `notification-fanout` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in notification-fanout, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `video-encoder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream search-suggest timeout, not video-encoder
  **action:** disable feature flag svc.video-encoder.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream session-store timeout, not video-encoder
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `video-encoder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in video-encoder, not what the agent said**.
>
> Recommended first action: `increase video-encoder concurrency limit to 2x and re-rate-limit upstream`

---

## `cart-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** DNS resolution lag in the cart-service sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** page the notification-fanout oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `cart-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cart-service, not what the agent said**.
>
> Recommended first action: `increase cart-service concurrency limit to 2x and re-rate-limit upstream`

---

## `price-cache` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream recommend-feed timeout, not price-cache
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the price-cache sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the price-cache sidecar

### Suggested runbook entry

> When `price-cache` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `live-stream-edge` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not live-stream-edge
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the live-stream-edge sidecar

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said
  **action:** disable feature flag svc.live-stream-edge.new_path

### Suggested runbook entry

> When `live-stream-edge` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `notification-fanout` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the notification-fanout sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream auth-service timeout, not notification-fanout
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `notification-fanout` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `page the session-store oncall; the real ownership is downstream`

---

## `notification-fanout` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream search-suggest timeout, not notification-fanout
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not notification-fanout
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** no actionable signal found
  **oncall:** actually a downstream notification-fanout timeout, not notification-fanout

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar

### Suggested runbook entry

> When `notification-fanout` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the notification-fanout sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `auth-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream ad-bidder timeout, not auth-service
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the auth-service sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the auth-service sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `auth-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the auth-service sidecar**.
>
> Recommended first action: `increase auth-service concurrency limit to 2x and re-rate-limit upstream`

---

## `image-thumbnail` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream live-stream-edge timeout, not image-thumbnail
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `image-thumbnail` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `auth-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the auth-service sidecar
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** page the order-pipeline oncall; the real ownership is downstream

### Suggested runbook entry

> When `auth-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase auth-service concurrency limit to 2x and re-rate-limit upstream`

---

## `order-pipeline` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `order-pipeline` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the order-pipeline sidecar**.
>
> Recommended first action: `increase order-pipeline concurrency limit to 2x and re-rate-limit upstream`

---

## `live-stream-edge` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream order-pipeline timeout, not live-stream-edge
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `live-stream-edge` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in live-stream-edge, not what the agent said**.
>
> Recommended first action: `increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream`

---

## `cart-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** page the promo-engine oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** page the notification-fanout oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar

### Suggested runbook entry

> When `cart-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cart-service, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `comment-svc` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** actually a downstream price-cache timeout, not comment-svc
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream live-stream-edge timeout, not comment-svc

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

- **agent:** no actionable signal found
  **oncall:** actually a downstream comment-svc timeout, not comment-svc

### Suggested runbook entry

> When `comment-svc` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in comment-svc, not what the agent said**.
>
> Recommended first action: `increase comment-svc concurrency limit to 2x and re-rate-limit upstream`

---

## `comment-svc` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the comment-svc sidecar

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not comment-svc

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

### Suggested runbook entry

> When `comment-svc` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `checkout-api` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not checkout-api

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

### Suggested runbook entry

> When `checkout-api` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the checkout-api sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `promo-engine` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** page the image-thumbnail oncall; the real ownership is downstream

### Suggested runbook entry

> When `promo-engine` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase promo-engine concurrency limit to 2x and re-rate-limit upstream`

---

## `payments-gateway` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream comment-svc timeout, not payments-gateway
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream user-profile timeout, not payments-gateway
  **action:** disable feature flag svc.payments-gateway.new_path

### Suggested runbook entry

> When `payments-gateway` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in payments-gateway, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.payments-gateway.new_path`

---

## `search-suggest` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not search-suggest
  **action:** page the recommend-feed oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream promo-engine timeout, not search-suggest
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the search-suggest sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream image-thumbnail timeout, not search-suggest
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `search-suggest` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in search-suggest, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `inventory-sync` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not inventory-sync
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar

### Suggested runbook entry

> When `inventory-sync` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `increase inventory-sync concurrency limit to 2x and re-rate-limit upstream`

---

## `checkout-api` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream video-encoder timeout, not checkout-api
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream video-encoder timeout, not checkout-api
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream price-cache timeout, not checkout-api

- **agent:** {svc} health-check failure cascade
  **oncall:** actually a downstream promo-engine timeout, not checkout-api
  **action:** disable feature flag svc.checkout-api.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the search-suggest oncall; the real ownership is downstream

### Suggested runbook entry

> When `checkout-api` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **actually a downstream video-encoder timeout, not checkout-api**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `session-store` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream promo-engine timeout, not session-store
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for recommend-feed was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** page the ad-bidder oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the recommend-feed oncall; the real ownership is downstream

### Suggested runbook entry

> When `session-store` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **actually a downstream promo-engine timeout, not session-store**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `ad-bidder` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream cdn-router timeout, not ad-bidder
  **action:** disable feature flag svc.ad-bidder.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the ad-bidder sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream ad-bidder timeout, not ad-bidder

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `ad-bidder` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the ad-bidder sidecar**.
>
> Recommended first action: `disable feature flag svc.ad-bidder.new_path`

---

## `video-encoder` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the video-encoder sidecar
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream search-suggest timeout, not video-encoder
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream auth-service timeout, not video-encoder

### Suggested runbook entry

> When `video-encoder` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in video-encoder, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `session-store` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** disable feature flag svc.session-store.new_path

### Suggested runbook entry

> When `session-store` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the session-store sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `checkout-api` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the checkout-api sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the checkout-api sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `checkout-api` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the checkout-api sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `video-encoder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the video-encoder sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the video-encoder sidecar
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream notification-fanout timeout, not video-encoder
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `video-encoder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the video-encoder sidecar**.
>
> Recommended first action: `increase video-encoder concurrency limit to 2x and re-rate-limit upstream`

---

## `ad-bidder` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** actually a downstream checkout-api timeout, not ad-bidder
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `ad-bidder` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the ad-bidder sidecar**.
>
> Recommended first action: `increase ad-bidder concurrency limit to 2x and re-rate-limit upstream`

---

## `order-pipeline` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the order-pipeline sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said
  **action:** disable feature flag svc.order-pipeline.new_path

### Suggested runbook entry

> When `order-pipeline` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in order-pipeline, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `video-encoder` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the video-encoder sidecar
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `video-encoder` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `comment-svc` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the comment-svc sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream price-cache timeout, not comment-svc
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream video-encoder timeout, not comment-svc
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `comment-svc` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `disable feature flag svc.comment-svc.new_path`

---

## `user-profile` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the user-profile sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the user-profile sidecar

### Suggested runbook entry

> When `user-profile` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

