# Auto-drafted runbook entries

Generated at `1780940173526` (UTC ms).  
Each section below is **a draft** assembled from oncall corrections (`verdict ∈ thumbs_down|incorrect` with `correct_root_cause` set). Review before merging.

- **46** cluster(s) ready for review
- **203** cluster(s) below the `min_occurrences=5` threshold (suppressed)

---

## `inventory-sync` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **12** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for price-cache was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream notification-fanout timeout, not inventory-sync
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream video-encoder timeout, not inventory-sync
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the image-thumbnail oncall; the real ownership is downstream

_…and 2 more occurrences_

### Suggested runbook entry

> When `inventory-sync` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `cdn-router` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **11** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream notification-fanout timeout, not cdn-router
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** increase cdn-router concurrency limit to 2x and re-rate-limit upstream

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** page the rate-limiter-edge oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** restart the sidecar, not the main container

_…and 1 more occurrences_

### Suggested runbook entry

> When `cdn-router` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cdn-router, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `auth-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream recommend-feed timeout, not auth-service
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream order-pipeline timeout, not auth-service
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for payments-gateway was filling our partition
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `auth-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in auth-service, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.auth-service.new_path`

---

## `recommend-feed` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **9** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the recommend-feed sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** disable feature flag svc.recommend-feed.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for price-cache was filling our partition
  **action:** disable feature flag svc.recommend-feed.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream inventory-sync timeout, not recommend-feed
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `recommend-feed` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the recommend-feed sidecar**.
>
> Recommended first action: `disable feature flag svc.recommend-feed.new_path`

---

## `cart-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **8** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for recommend-feed was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream comment-svc timeout, not cart-service
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** no actionable signal found
  **oncall:** actually a downstream checkout-api timeout, not cart-service

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** page the notification-fanout oncall; the real ownership is downstream

### Suggested runbook entry

> When `cart-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cart-service, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `comment-svc` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the comment-svc sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream checkout-api timeout, not comment-svc
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `comment-svc` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `ad-bidder` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** no actionable signal found
  **oncall:** actually a downstream cdn-router timeout, not ad-bidder
  **action:** disable feature flag svc.ad-bidder.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream ad-bidder timeout, not ad-bidder

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** page the auth-service oncall; the real ownership is downstream

### Suggested runbook entry

> When `ad-bidder` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition**.
>
> Recommended first action: `disable feature flag svc.ad-bidder.new_path`

---

## `comment-svc` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not comment-svc
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** actually a downstream auth-service timeout, not comment-svc

### Suggested runbook entry

> When `comment-svc` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in comment-svc, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.comment-svc.new_path`

---

## `comment-svc` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream notification-fanout timeout, not comment-svc
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `comment-svc` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `inventory-sync` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream inventory-sync timeout, not inventory-sync
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `inventory-sync` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `inventory-sync` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream session-store timeout, not inventory-sync
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `inventory-sync` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the inventory-sync sidecar**.
>
> Recommended first action: `page the order-pipeline oncall; the real ownership is downstream`

---

## `user-profile` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.user-profile.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream promo-engine timeout, not user-profile
  **action:** page the notification-fanout oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream checkout-api timeout, not user-profile
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not user-profile
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** actually a downstream inventory-sync timeout, not user-profile
  **action:** disable feature flag svc.user-profile.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the user-profile sidecar

### Suggested runbook entry

> When `user-profile` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase user-profile concurrency limit to 2x and re-rate-limit upstream`

---

## `payments-gateway` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the promo-engine oncall; the real ownership is downstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `payments-gateway` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the payments-gateway sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `live-stream-edge` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream auth-service timeout, not live-stream-edge
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream promo-engine timeout, not live-stream-edge
  **action:** page the user-profile oncall; the real ownership is downstream

### Suggested runbook entry

> When `live-stream-edge` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in live-stream-edge, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `notification-fanout` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream rate-limiter-edge timeout, not notification-fanout
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream user-profile timeout, not notification-fanout

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream rate-limiter-edge timeout, not notification-fanout
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

### Suggested runbook entry

> When `notification-fanout` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in notification-fanout, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.notification-fanout.new_path`

---

## `price-cache` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `price-cache` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase price-cache concurrency limit to 2x and re-rate-limit upstream`

---

## `cart-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** actually a downstream inventory-sync timeout, not cart-service
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for price-cache was filling our partition
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream order-pipeline timeout, not cart-service
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `cart-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cart-service, not what the agent said**.
>
> Recommended first action: `increase cart-service concurrency limit to 2x and re-rate-limit upstream`

---

## `cdn-router` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase cdn-router concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `cdn-router` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in cdn-router, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `order-pipeline` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream session-store timeout, not order-pipeline
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream comment-svc timeout, not order-pipeline

### Suggested runbook entry

> When `order-pipeline` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the order-pipeline sidecar**.
>
> Recommended first action: `increase order-pipeline concurrency limit to 2x and re-rate-limit upstream`

---

## `rate-limiter-edge` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in rate-limiter-edge, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream payments-gateway timeout, not rate-limiter-edge
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar
  **action:** page the ad-bidder oncall; the real ownership is downstream

### Suggested runbook entry

> When `rate-limiter-edge` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the rate-limiter-edge sidecar**.
>
> Recommended first action: `disable feature flag svc.rate-limiter-edge.new_path`

---

## `ad-bidder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream order-pipeline timeout, not ad-bidder
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

### Suggested runbook entry

> When `ad-bidder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `rate-limiter-edge` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream rate-limiter-edge timeout, not rate-limiter-edge

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in rate-limiter-edge, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream ad-bidder timeout, not rate-limiter-edge

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream video-encoder timeout, not rate-limiter-edge

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** _(not recorded)_
  **oncall:** actually a downstream inventory-sync timeout, not rate-limiter-edge

### Suggested runbook entry

> When `rate-limiter-edge` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **actually a downstream rate-limiter-edge timeout, not rate-limiter-edge**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `comment-svc` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream auth-service timeout, not comment-svc
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream notification-fanout timeout, not comment-svc
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `comment-svc` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in comment-svc, not what the agent said**.
>
> Recommended first action: `increase comment-svc concurrency limit to 2x and re-rate-limit upstream`

---

## `live-stream-edge` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the live-stream-edge sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** disable feature flag svc.live-stream-edge.new_path

### Suggested runbook entry

> When `live-stream-edge` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the live-stream-edge sidecar**.
>
> Recommended first action: `increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream`

---

## `search-suggest` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** disable feature flag svc.search-suggest.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream session-store timeout, not search-suggest
  **action:** disable feature flag svc.search-suggest.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `search-suggest` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in search-suggest, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.search-suggest.new_path`

---

## `inventory-sync` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the inventory-sync sidecar

### Suggested runbook entry

> When `inventory-sync` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the inventory-sync sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `notification-fanout` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not notification-fanout

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the promo-engine oncall; the real ownership is downstream

### Suggested runbook entry

> When `notification-fanout` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in notification-fanout, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.notification-fanout.new_path`

---

## `ad-bidder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream inventory-sync timeout, not ad-bidder
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream search-suggest timeout, not ad-bidder
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream recommend-feed timeout, not ad-bidder
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `ad-bidder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `checkout-api` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** _(not recorded)_
  **oncall:** actually a downstream notification-fanout timeout, not checkout-api

### Suggested runbook entry

> When `checkout-api` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the checkout-api sidecar**.
>
> Recommended first action: `increase checkout-api concurrency limit to 2x and re-rate-limit upstream`

---

## `image-thumbnail` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

### Suggested runbook entry

> When `image-thumbnail` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `live-stream-edge` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the comment-svc oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not live-stream-edge
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said

- **agent:** no actionable signal found
  **oncall:** actually a downstream search-suggest timeout, not live-stream-edge

### Suggested runbook entry

> When `live-stream-edge` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `page the comment-svc oncall; the real ownership is downstream`

---

## `payments-gateway` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the price-cache oncall; the real ownership is downstream

### Suggested runbook entry

> When `payments-gateway` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in payments-gateway, not what the agent said**.
>
> Recommended first action: `increase payments-gateway concurrency limit to 2x and re-rate-limit upstream`

---

## `promo-engine` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar

- **agent:** _(not recorded)_
  **oncall:** actually a downstream cdn-router timeout, not promo-engine
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.promo-engine.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `promo-engine` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `user-profile` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.user-profile.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the user-profile sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the user-profile sidecar
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `user-profile` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `cart-service` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream search-suggest timeout, not cart-service

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `cart-service` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `auth-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** page the order-pipeline oncall; the real ownership is downstream

### Suggested runbook entry

> When `auth-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `page the checkout-api oncall; the real ownership is downstream`

---

## `video-encoder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the video-encoder sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream promo-engine timeout, not video-encoder
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream notification-fanout timeout, not video-encoder
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `video-encoder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the video-encoder sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `payments-gateway` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `payments-gateway` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in payments-gateway, not what the agent said**.
>
> Recommended first action: `increase payments-gateway concurrency limit to 2x and re-rate-limit upstream`

---

## `rate-limiter-edge` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** disable feature flag svc.rate-limiter-edge.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the rate-limiter-edge sidecar

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `rate-limiter-edge` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `user-profile` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the user-profile sidecar

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not user-profile
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream image-thumbnail timeout, not user-profile

### Suggested runbook entry

> When `user-profile` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in user-profile, not what the agent said**.
>
> Recommended first action: `increase user-profile concurrency limit to 2x and re-rate-limit upstream`

---

## `payments-gateway` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream search-suggest timeout, not payments-gateway
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for payments-gateway was filling our partition
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream recommend-feed timeout, not payments-gateway
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `payments-gateway` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the payments-gateway sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `price-cache` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not price-cache
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for recommend-feed was filling our partition
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream comment-svc timeout, not price-cache
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `price-cache` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **actually a downstream user-profile timeout, not price-cache**.
>
> Recommended first action: `increase price-cache concurrency limit to 2x and re-rate-limit upstream`

---

## `cdn-router` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream auth-service timeout, not cdn-router
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cdn-router sidecar

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** page the session-store oncall; the real ownership is downstream

### Suggested runbook entry

> When `cdn-router` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the cdn-router sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `video-encoder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

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

## `checkout-api` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.checkout-api.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream inventory-sync timeout, not checkout-api
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `checkout-api` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `notification-fanout` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `notification-fanout` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `disable feature flag svc.notification-fanout.new_path`

---

