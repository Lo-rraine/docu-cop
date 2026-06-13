# HttpOnly Cookie Authentication Implementation

## Overview

This document summarizes the changes to implement HttpOnly Secure SameSite cookie-based authentication for Document Copilot, with fallback support for Authorization headers during migration.

**Status:** ✅ **Backend Complete**, 🟡 **Frontend Updated (Ready for SignIn component update)**

---

## Backend Changes ✅

### Files Modified

#### 1. `backend/app/config.py`
**Change:** Added environment configuration
```python
environment: str = "development"  # Set to "production" in production
```
**Purpose:** Determine whether to enforce HTTPS for cookies

#### 2. `backend/app/main.py`
**Changes:**
- Imported `JSONResponse` and `verify_password`
- Updated `/auth/register` endpoint:
  - Generates JWT (unchanged)
  - Sets JWT as HttpOnly cookie instead of returning in body
  - Returns `{"success": true, "email": user.email}`
  
- Updated `/auth/login` endpoint:
  - Same behavior as register
  
- Added `/auth/logout` endpoint:
  - Clears the `access_token` cookie

- Marked `/auth/token` as deprecated (kept for development)

**Cookie Configuration:**
```python
response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,                              # JavaScript cannot access
    secure=settings.environment == "production",  # HTTPS in production only
    samesite="lax",                             # CSRF protection
    max_age=86400,                              # 24 hours
    path="/",
)
```

#### 3. `backend/app/auth/dependencies.py`
**Changes:**
- Updated `get_current_user()` to support dual token sources:
  1. **Primary:** HttpOnly cookie (`request.cookies.get("access_token")`)
  2. **Fallback:** Authorization header (for API clients & migration)
- Same JWT verification logic
- Still creates/retrieves user automatically

---

## Frontend Changes ✅

### Files Modified

#### 1. `frontend/src/lib/auth.ts`
**Removed:**
- `getToken()`, `setToken()`, `clearToken()` (localStorage no longer used)
- `signInWithEmail()` (development endpoint)

**Added:**
- `register(email, password)` — Registration with automatic sign-in
- `login(email, password)` — Login with credentials
- `logout()` — Clear authentication cookie
- `isAuthenticated()` — Check if user has valid cookie/session

**All functions now:**
- Use `credentials: 'include'` to enable cookie transmission
- No longer manage token in localStorage
- Browser automatically handles HttpOnly cookies

#### 2. `frontend/src/lib/http.ts`
**Changes:**
- Removed `getToken()` import
- Added `credentials: 'include'` to all fetch requests
- Removed manual Authorization header injection
- Cookies are sent automatically by browser

**Before:**
```typescript
headers['Authorization'] = `Bearer ${token}`
```

**After:**
```typescript
credentials: 'include'  // Browser sends cookies automatically
```

#### 3. `frontend/src/lib/auth-context.tsx`
**Changes:**
- Updated `checkAuth()` to use new async `isAuthenticated()`
- Added try/catch for authentication check
- Kept `refreshAuth()` pattern for context updates
- User state management unchanged

---

## CORS Configuration

**Already Configured in `backend/app/main.py`:**
```python
CORSMiddleware(
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,  # ✅ This enables cookie credentials
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**No CORS changes needed** — `allow_credentials=True` is already set.

---

## Cookie Configuration Summary

| Property | Value | Purpose |
|----------|-------|---------|
| `name` | `access_token` | Identifies the cookie |
| `httponly` | `true` | Prevents JavaScript access (XSS protection) |
| `secure` | `true` (prod) / `false` (dev) | HTTPS-only in production |
| `samesite` | `lax` | CSRF protection; allows top-level navigations |
| `max_age` | `86400` (24 hours) | Token expiration |
| `path` | `/` | Available for all routes |

---

## Manual Testing Steps

### Prerequisites
- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:5173`
- Database with migrations applied

### Test 1: Register → Automatic Sign-In → /me

```bash
# 1. Register (creates user, sets cookie, returns success)
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"password123"}'

# Expected Response (200 OK):
# Set-Cookie: access_token=eyJ...; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400
# {"success":true,"email":"test1@example.com"}

# 2. Call /me with cookie (cookie automatically sent by curl with -b flag)
curl -i -X GET http://localhost:8000/me \
  -b "access_token=<token_from_header>" \
  -H "Content-Type: application/json"

# Expected Response (200 OK):
# {"id":"...","email":"test1@example.com"}
```

### Test 2: Login with Correct Credentials

```bash
# 1. Login (sets cookie)
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"password123"}'

# Expected Response (200 OK):
# Set-Cookie: access_token=eyJ...; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400
# {"success":true,"email":"test1@example.com"}

# 2. Verify with /me
curl -X GET http://localhost:8000/me \
  -b "access_token=<token>"
```

### Test 3: Login with Wrong Password

```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"wrongpassword"}'

# Expected Response (401 Unauthorized):
# {"detail":"Invalid email or password"}
```

### Test 4: Logout

```bash
# 1. Logout (clears cookie)
curl -i -X POST http://localhost:8000/auth/logout

# Expected Response (200 OK):
# Set-Cookie: access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/
# {"success":true}

# 2. Try /me (should fail - no cookie)
curl -X GET http://localhost:8000/me

# Expected Response (401 Unauthorized):
# {"detail":"Not authenticated"}
```

### Test 5: Authorization Header Fallback (Migration Support)

```bash
# Get a token via old dev endpoint
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?email=testuser@example.com" | jq -r '.access_token')

# Use token via Authorization header (should still work)
curl -X GET http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"

# Expected Response (200 OK):
# {"id":"...","email":"testuser@example.com"}
```

---

## Frontend SignIn Component Update (Not Yet Implemented)
q
The `frontend/src/pages/SignIn.tsx` still uses the deprecated `signInWithEmail()` function from the old dev endpoint.

**To complete the migration, update SignIn.tsx:**

```typescript
// OLD (still uses deprecated /auth/token endpoint)
import { signInWithEmail } from '@/lib/auth'

// NEW (should use new register/login functions)
import { register, login } from '@/lib/auth'

// For development/MVP, can use register() which auto-signs in:
async function handleSignIn(e: React.FormEvent) {
  e.preventDefault()
  setError('')
  setLoading(true)

  // Try registration (new user or existing)
  let result = await register(email, password)
  
  // If already registered, fall back to login
  if (result.error?.message.includes('already registered')) {
    result = await login(email, password)
  }

  if (result.error) {
    setError(result.error.message)
    setLoading(false)
  } else {
    await refreshAuth()
    navigate('/')
  }
}
```

---

## Gradual Migration Strategy

The implementation supports gradual migration:

1. **Phase 1 (Current):** ✅ Backend sets cookies, frontend reads localStorage (via Authorization header fallback)
2. **Phase 2 (Next):** Update SignIn component to use `register()`/`login()` functions
3. **Phase 3 (Current):** ✅ AI SDK-compatible streaming + complete cookie enforcement

**During migration:**
- `/auth/register` and `/auth/login` return cookies
- `/auth/token` still works for dev/testing (legacy support)
- `get_current_user()` accepts both cookies and headers for backward compatibility
- Chat streaming endpoint (`/chat/stream`) enforces cookies only and uses AI SDK message format

---

## Security Summary

| Attack | localStorage | sessionStorage | HttpOnly Cookies |
|--------|--------------|----------------|------------------|
| XSS Token Theft | ❌ Vulnerable | ❌ Vulnerable | ✅ Protected |
| CSRF | ✅ Safe | ✅ Safe | ✅ Protected |
| Token Persistence | ✅ Persisted | ❌ Lost on close | ✅ Persisted |

**HttpOnly Cookies are best** because:
- ✅ XSS attacker cannot steal token via JavaScript
- ✅ CSRF protected via SameSite=Lax
- ✅ Token automatically sent by browser
- ✅ No manual header management needed

---

## Environment Variables

Add to `.env` (backend):
```bash
ENVIRONMENT=development  # Set to "production" for HTTPS cookies
```

In production, ensure:
- `ENVIRONMENT=production` (forces `secure=True` on cookies)
- All traffic is HTTPS
- `allowed_origins` includes your frontend domain

---

## Phase 3: AI SDK Streaming + Complete Cookie Enforcement

**Status:** ✅ **Complete (Backend + Frontend)**

### Changes Implemented

#### 1. Chat Streaming Endpoint (`backend/app/api/chat.py`)
**Enforcement:** HttpOnly cookie authentication only (no Authorization header fallback)

```python
def get_current_user_from_cookies(request: Request, db: Session) -> User:
    """Extract current user from HttpOnly cookie only.
    
    Phase 3 enforcement: streaming endpoints require cookies.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # ... verify JWT and return user
```

**Streaming Format:** AI SDK-compatible Server-Sent Events
- Text tokens: `0:"<token>"`  (message start code + text)
- Data parts: `d:{json}`        (structured data like citations)
- Errors: `e:"<error>"`         (error events)

```python
async def token_generator():
    try:
        for word in stub.split():
            chunk = word + " "
            yield f"0:{json.dumps(chunk)}\n"  # AI SDK text format
            await asyncio.sleep(0.05)
        # Persist after streaming completes
        db.add(ChatMessage(...))
    except Exception as e:
        yield f"e:{json.dumps(str(e))}\n"  # AI SDK error format
```

**Architecture Alignment:**
- Cookies are the primary and only authentication mechanism for streaming
- Streaming response format matches Vercel AI SDK expectations
- Allows frontend AI SDK client (`useChat()`) to work seamlessly with cookies and `credentials: 'include'`
- No manual Authorization header management needed in streaming context

#### 2. Authentication Layering
**General endpoints** (`/me`, `/threads`, `/threads/{id}/messages`, etc.):
- Use `get_current_user()` which accepts both cookies and Authorization headers
- Supports gradual migration and API client compatibility
- No changes required

**Streaming endpoints** (`/chat/stream`):
- Use `get_current_user_from_cookies()` which enforces cookies only
- Future-proofs the architecture: streaming auth is always cookie-based
- AI SDK client in browser always sends cookies with `credentials: 'include'`

#### 3. Why This Matters for AI SDK
The Vercel AI SDK (`@vercel/ai`) expects:
- **Authentication:** Automatic cookie transmission via `credentials: 'include'`
- **Streaming Format:** Server-Sent Events with specific message codes (0 for text, d for data, e for errors)
- **Message Contract:** `useChat()` hook parses these codes and updates UI state

By enforcing cookies and using AI SDK-compatible message format in Phase 3:
- Frontend `useChat()` hook receives properly formatted events
- No manual token management or Authorization header injection in streaming
- Streaming state is managed entirely by the AI SDK
- Chat UI updates automatically as tokens arrive

### Test Plan

#### Manual Testing: Streaming with Cookies

1. **Ensure cookies are set:**
```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
# Note the Set-Cookie header with access_token
```

2. **Stream with curl (cookie auto-sent):**
```bash
curl -i -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"id":"<thread-uuid>","messages":[{"role":"user","content":"test"}]}' \
  -b "access_token=<token-from-login>"
# Verify response is text/event-stream with format: 0:"<token>"
```

3. **Verify Authorization header fallback is NOT accepted:**
```bash
curl -i -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"id":"<thread-uuid>","messages":[...]}'
# Expected: 401 Unauthorized (no fallback)
```

4. **Verify AI SDK format:**
```
Response stream should contain:
0:"This "
0:"is "
0:"a "
...
```
Not the old format: `data: This data: is data: a`

### Frontend Integration (Unchanged)

The frontend `useChat()` hook already handles this correctly:
```typescript
const { messages, sendMessage } = useChat({
  id: threadId,
  api: `${apiBaseUrl}/chat/stream`,
  credentials: 'include',  // Cookies sent automatically
});
// Hook parses 0:"token" format and updates messages
```

### Migration Checklist

- [x] Chat endpoint uses `get_current_user_from_cookies()` 
- [x] Streaming response uses AI SDK message format (0: for text, d: for data, e: for errors)
- [x] `/auth/token` kept as legacy dev endpoint
- [x] Test complete flow: Register → Chat stream → verify AI SDK receives tokens
- [x] Verify frontend correctly parses streamed events (0/d/e format)
- [x] Document in architecture.md that streaming auth is cookie-only
- [x] Frontend chat page with thread management
- [x] Cookie enforcement verified (no Authorization header fallback for streaming)

### Long-Term Path (Future Phase)

Once Phase 3 is verified and Phase 2 (SignIn update) is complete:
- Remove `/auth/token` dev endpoint
- Remove Authorization header fallback from general `get_current_user()` if desired
- Update architecture.md to mark cookie-based auth as standard for all endpoints

## Completed (Phase 3 Summary)

1. ✅ Backend streaming implementation with cookie enforcement
2. ✅ Frontend utility functions (auth with cookies)
3. ✅ Update `frontend/src/pages/SignIn.tsx` to use `register()` and `login()` (Phase 2)
4. ✅ Test streaming with AI SDK format — verified `0:"token"` format works end-to-end
5. ✅ Frontend chat interface with real-time token streaming and message updates
6. ✅ Thread management (create, list threads)
7. ✅ Cookie enforcement verified (401 response without cookie)

## What Works Now

- ✅ User registration/login with HttpOnly cookies
- ✅ Chat thread creation and listing
- ✅ Streaming endpoint emits AI SDK-compatible format (`0:"token"`)
- ✅ Frontend parses streaming events correctly
- ✅ Real-time message updates in chat UI
- ⚠️ **Currently showing stubbed response** — next phase is PydanticAI integration

## Next Phase (Phase 4: LLM Integration)

The streaming infrastructure is complete. Next steps:
1. Replace `"This is a stubbed assistant reply."` with PydanticAI agent
2. Integrate retrieval (pgvector + full-text search)
3. Add citation handling via `d:` data events
4. Implement grounding validation
5. Deploy and monitor
