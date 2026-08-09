## Request Types

## GET
This is used when we want to fetch a resource/data from the backend.

## POST
This is used when we want to create a new resource in the backend.

## PUT
This is used when we want to update an existing resource in the backend.

## DELETE
This is used when we want to delete an existing resource in the backend.

## PATCH
This is used when we want to update an existing resource partially in the backend.


`GET /users/101`
```json
{
  "id": 101,
  "name": "Shantanu",
  "email": "shantanu@example.com",
  "age": 27,
  "city": "Bangalore"
}
```

To Update:

`PUT /users/101`
```json
{
  "name": "Shantanu Shubham",
  "email": "shantanu@example.com",
  "age": 28,
  "city": "Bangalore"
}
```

To Partial Update:

`PATCH /users/101`
```json
{
  "name": "Shantanu Shubham"
}
```



# Data in Request

## Body

## Query Parameter aka Request Parameter
This is appended to the URL. This is non-mandatory data. It doesn't conribute to the URL signature of the request.

Example: /add?a=10&b=5

## Path Parameter
This is appended to the URL. This is mandatory data. It does conribute to the URL signature of the request.

Example: GET /users/:user-id --> /users/101

## Header
This is key-value pair. This is usually mandatory data. It contains information related to auth and the type of request response, and some other information.