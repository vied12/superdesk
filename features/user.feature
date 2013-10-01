@wip
Feature: User Resource

    @auth
    Scenario: Create a user
        Given empty "users"
        When we post to "/users"
            """
            {"username": "foo", "password": "bar"}
            """

        Then we get new resource
            """
            {"username": "foo", "_links": {"self": {"href": "/users/foo"}}}
            """
        And we get no "password"

    @auth
    Scenario: List users
        Given "users"
            """
            [{"username": "foo"}, {"username": "bar"}]
            """

        When we get "/users"
        Then we get list with 2 items

    @auth
    Scenario: Fetch single user
        Given "users"
            """
            {"username": "foo"}
            """

        When we get "/users/foo"
        Then we get existing resource
            """
            {"username": "foo"}
            """

    @auth
    Scenario: Delete user
        Given "users"
            """
            {"username": "foo"}
            """

        When we delete "/users/foo"
        Then we get OK response

    @auth
    Scenario: Update user
        Given "users"
            """
            {"username": "foo"}
            """

        When we patch "/users/foo"
            """
            {"first_name": "Foo"}
            """

        Then we get updated response
