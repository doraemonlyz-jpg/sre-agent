# Auto-drafted runbook entries

Generated at `1782127829772` (UTC ms).  
Each section below is **a draft** assembled from oncall corrections (`verdict ∈ thumbs_down|incorrect` with `correct_root_cause` set). Review before merging.

- **38** cluster(s) ready for review
- **222** cluster(s) below the `min_occurrences=5` threshold (suppressed)

---

## `cart-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **13** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the cart-service sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream video-encoder timeout, not cart-service

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** disable feature flag svc.cart-service.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** restart the sidecar, not the main container

_…and 3 more occurrences_

### Suggested runbook entry

> When `cart-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `video-encoder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **10** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.video-encoder.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream search-suggest timeout, not video-encoder

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `video-encoder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `session-store` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **10** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the session-store sidecar

- **agent:** no actionable signal found
  **oncall:** actually a downstream notification-fanout timeout, not session-store

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not session-store
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** page the recommend-feed oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `session-store` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the session-store sidecar**.
>
> Recommended first action: `increase session-store concurrency limit to 2x and re-rate-limit upstream`

---

## `user-profile` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **10** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream ad-bidder timeout, not user-profile

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not user-profile
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the user-profile sidecar

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `user-profile` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase user-profile concurrency limit to 2x and re-rate-limit upstream`

---

## `session-store` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** actually a downstream order-pipeline timeout, not session-store
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream cdn-router timeout, not session-store

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not session-store
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `session-store` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in session-store, not what the agent said**.
>
> Recommended first action: `increase session-store concurrency limit to 2x and re-rate-limit upstream`

---

## `notification-fanout` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **9** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `notification-fanout` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the notification-fanout sidecar**.
>
> Recommended first action: `disable feature flag svc.notification-fanout.new_path`

---

## `image-thumbnail` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the rate-limiter-edge oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `image-thumbnail` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `page the rate-limiter-edge oncall; the real ownership is downstream`

---

## `cart-service` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream notification-fanout timeout, not cart-service
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cdn-router timeout, not cart-service
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream search-suggest timeout, not cart-service

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `cart-service` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **actually a downstream notification-fanout timeout, not cart-service**.
>
> Recommended first action: `increase cart-service concurrency limit to 2x and re-rate-limit upstream`

---

## `inventory-sync` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **8** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream order-pipeline timeout, not inventory-sync
  **action:** disable feature flag svc.inventory-sync.new_path

### Suggested runbook entry

> When `inventory-sync` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `page the price-cache oncall; the real ownership is downstream`

---

## `payments-gateway` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **7** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** no actionable signal found
  **oncall:** actually a downstream checkout-api timeout, not payments-gateway
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream checkout-api timeout, not payments-gateway
  **action:** page the user-profile oncall; the real ownership is downstream

### Suggested runbook entry

> When `payments-gateway` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the payments-gateway sidecar**.
>
> Recommended first action: `disable feature flag svc.payments-gateway.new_path`

---

## `session-store` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **7** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** {svc} health-check failure cascade
  **oncall:** actually a downstream recommend-feed timeout, not session-store
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream checkout-api timeout, not session-store

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not session-store
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `session-store` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in session-store, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `image-thumbnail` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `image-thumbnail` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `page the price-cache oncall; the real ownership is downstream`

---

## `auth-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the auth-service sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** actually a downstream rate-limiter-edge timeout, not auth-service
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream recommend-feed timeout, not auth-service
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream payments-gateway timeout, not auth-service
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the auth-service sidecar
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `auth-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the auth-service sidecar**.
>
> Recommended first action: `increase auth-service concurrency limit to 2x and re-rate-limit upstream`

---

## `auth-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream ad-bidder timeout, not auth-service
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream order-pipeline timeout, not auth-service
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream order-pipeline timeout, not auth-service
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the auth-service sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `auth-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **actually a downstream order-pipeline timeout, not auth-service**.
>
> Recommended first action: `increase auth-service concurrency limit to 2x and re-rate-limit upstream`

---

## `checkout-api` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream auth-service timeout, not checkout-api
  **action:** disable feature flag svc.checkout-api.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the checkout-api sidecar

### Suggested runbook entry

> When `checkout-api` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `promo-engine` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not promo-engine

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `promo-engine` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase promo-engine concurrency limit to 2x and re-rate-limit upstream`

---

## `comment-svc` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream inventory-sync timeout, not comment-svc
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the comment-svc sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** page the order-pipeline oncall; the real ownership is downstream

### Suggested runbook entry

> When `comment-svc` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `disable feature flag svc.comment-svc.new_path`

---

## `checkout-api` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream rate-limiter-edge timeout, not checkout-api
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream comment-svc timeout, not checkout-api
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** page the recommend-feed oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream promo-engine timeout, not checkout-api
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `checkout-api` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in checkout-api, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `ad-bidder` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition

### Suggested runbook entry

> When `ad-bidder` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the ad-bidder sidecar**.
>
> Recommended first action: `page the cdn-router oncall; the real ownership is downstream`

---

## `promo-engine` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** page the recommend-feed oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not promo-engine

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** {svc} health-check failure cascade
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `promo-engine` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `live-stream-edge` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the comment-svc oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not live-stream-edge

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `live-stream-edge` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `live-stream-edge` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** _(not recorded)_
  **oncall:** actually a downstream rate-limiter-edge timeout, not live-stream-edge
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in live-stream-edge, not what the agent said
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not live-stream-edge
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition
  **action:** disable feature flag svc.live-stream-edge.new_path

### Suggested runbook entry

> When `live-stream-edge` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `disable feature flag svc.live-stream-edge.new_path`

---

## `price-cache` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the price-cache sidecar
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the price-cache sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `price-cache` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the price-cache sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `search-suggest` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar
  **action:** disable feature flag svc.search-suggest.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream payments-gateway timeout, not search-suggest

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar
  **action:** disable feature flag svc.search-suggest.new_path

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said

### Suggested runbook entry

> When `search-suggest` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in search-suggest, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.search-suggest.new_path`

---

## `inventory-sync` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** no actionable signal found
  **oncall:** actually a downstream video-encoder timeout, not inventory-sync
  **action:** restart the sidecar, not the main container

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

## `notification-fanout` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream ad-bidder timeout, not notification-fanout
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not notification-fanout
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `notification-fanout` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in notification-fanout, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `recommend-feed` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream inventory-sync timeout, not recommend-feed

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `recommend-feed` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in recommend-feed, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `image-thumbnail` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `image-thumbnail` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `inventory-sync` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** {svc} health-check failure cascade
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `inventory-sync` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `ad-bidder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the ad-bidder sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the ad-bidder sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream payments-gateway timeout, not ad-bidder

### Suggested runbook entry

> When `ad-bidder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the ad-bidder sidecar**.
>
> Recommended first action: `page the user-profile oncall; the real ownership is downstream`

---

## `cdn-router` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cdn-router timeout, not cdn-router

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream recommend-feed timeout, not cdn-router
  **action:** increase cdn-router concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream live-stream-edge timeout, not cdn-router
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `cdn-router` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the cdn-router sidecar**.
>
> Recommended first action: `page the payments-gateway oncall; the real ownership is downstream`

---

## `comment-svc` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** page the promo-engine oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** page the live-stream-edge oncall; the real ownership is downstream

### Suggested runbook entry

> When `comment-svc` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `disable feature flag svc.comment-svc.new_path`

---

## `session-store` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the session-store sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `session-store` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in session-store, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `price-cache` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase price-cache concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** actually a downstream order-pipeline timeout, not price-cache
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the price-cache sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `price-cache` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `user-profile` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said
  **action:** page the ad-bidder oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the user-profile sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream user-profile timeout, not user-profile

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said

### Suggested runbook entry

> When `user-profile` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in user-profile, not what the agent said**.
>
> Recommended first action: `page the ad-bidder oncall; the real ownership is downstream`

---

## `comment-svc` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not comment-svc
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `comment-svc` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `cdn-router` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream comment-svc timeout, not cdn-router
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

### Suggested runbook entry

> When `cdn-router` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `promo-engine` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream notification-fanout timeout, not promo-engine
  **action:** disable feature flag svc.promo-engine.new_path

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.promo-engine.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `promo-engine` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in promo-engine, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.promo-engine.new_path`

---

