# HTTP Status Codes — Usage

## 1. 200 OK

**Meaning:** The request succeeded.

**When to use:**
- A `GET` request returns data successfully (e.g. fetching a user profile).
- A `PUT` or `PATCH` request updates a resource and you return the updated data.
- A `POST` request completes an action that does not create a new resource (e.g. login, send email).

**Example (Django REST Framework):**
```python
return Response({"message": "Hello from AirTribe"})  # defaults to 200
```

---

## 2. 201 Created

**Meaning:** The request succeeded and a **new resource** was created.

**When to use:**
- After a successful `POST` that creates something new (user, blog post, order, etc.).
- The response often includes the created object and/or a `Location` header pointing to the new resource.

**Example:**
```python
return Response(serializer.data, status=status.HTTP_201_CREATED)
```

---

## 3. 400 Bad Request

**Meaning:** The server cannot process the request because of a **client-side error** — invalid input, missing fields, or bad syntax.

**When to use:**
- Required query parameters or body fields are missing.
- Data fails validation (invalid email, negative age, etc.).
- Wrong data type (e.g. passing `"abc"` where a number is expected).

**Example:**
```python
# Missing query params in add_two_numbers
return Response({"error": "Both 'a' and 'b' are required."}, status=400)
```

---

## 4. Client Error Codes

### 401 Unauthorized

**Meaning:** Authentication is required or has **failed**.

**When to use:**
- No auth token or session was provided.
- Invalid or expired credentials (wrong password, expired JWT).

**Example:** User hits a protected endpoint without logging in.

---

### 403 Forbidden

**Meaning:** The client is authenticated, but **does not have permission** to access the resource.

**When to use:**
- A logged-in user tries to delete another user's account.
- A regular user tries to access an admin-only endpoint.

**Note:** 401 = "who are you?"; 403 = "I know who you are, but you can't do this."

---

### 404 Not Found

**Meaning:** The requested **resource does not exist** at that URL.

**When to use:**
- Requesting `/api/users/999` when user 999 does not exist.
- Hitting a URL that is not defined in your routes.

**Example:**
```python
return Response({"error": "User not found."}, status=404)
```

---

### 413 Payload Too Large

**Meaning:** The request body is **larger than the server is willing to accept**.

**When to use:**
- Uploading a file that exceeds the server's size limit.
- Sending a JSON body that is too big.

**Example:** Uploading a 50 MB image when the limit is 10 MB.

---

## 5. Server & Gateway Errors

### 500 Internal Server Error

**Meaning:** Something went wrong **on the server** — an unhandled exception or bug.

**When to use (return explicitly when catching errors):**
- Database connection failure.
- Unexpected code crash (e.g. unhandled `ZeroDivisionError`).

**Example:**
```python
return Response({"error": "Something went wrong."}, status=500)
```

---

### 502 Bad Gateway

**Meaning:** The server (acting as a **gateway or proxy**) received an **invalid response** from an upstream server it depends on.

**When it appears:**
- Your API calls another service (payment gateway, microservice) and that service is down or returns garbage.
- A reverse proxy (e.g. Nginx) cannot reach your Django app.

**Note:** Usually returned by infrastructure (Nginx, load balancer), not by your view code directly.

---

### 504 Gateway Timeout

**Meaning:** The gateway/proxy did not receive a timely response from the upstream server.

**When it appears:**
- Your Django view or an external API it calls takes too long to respond.
- Database query hangs beyond the proxy timeout.

**Related:** **408 Request Timeout** — the server timed out waiting for the **client** to send the full request (slow upload).

---

## 6. Browser / Network Errors (not always HTTP status codes)

These often show up in the browser or HTTP client instead of as a clean JSON response from your API.

### Request Timed Out

**Meaning:** No response was received within the allowed time.

**Common causes:**
- Server is overloaded or crashed.
- Network is slow or disconnected.
- Upstream service is unresponsive (may surface as 504 Gateway Timeout on the server side).

---

### Too Many Redirects

**Meaning:** The browser followed too many redirects (usually a **redirect loop**).

**Common causes:**
- `http` → `https` → `http` loop in URL config.
- Login page redirects to dashboard, which redirects back to login endlessly.

**Fix:** Check `urls.py`, middleware, and auth redirect settings — not a status code you return from a view.
