# Quick Start
The example below will guide you through the basics of creating a notebook, adding content, executing code, and seeing the output. For more examples, see our [Use Cases](../usage.md) section.

!!! note "Developer note: For pre-1.0 release information, see the [pre-1.0 README](https://github.com/noteable-io/origami/blob/release/0.0.35/README.md)"

--8<-- "README.md:install"

## API Tokens
--8<-- "README.md:api-tokens"

## Setting up the `APIClient`
--8<-- "README.md:api-client"

## Checking your user information
--8<-- "README.md:user-info"

## Creating a new Notebook

!!! note "For this example, we're using the `origamist_default_project_id`, which is the default project designed to be used by the ChatGPT plugin. Feel free to replace it with projects you have access to in [Noteable](https://app.noteable.io/)!"

--8<-- "README.md:create-notebook"

## Launching a Kernel

--8<-- "README.md:launch-kernel"

## Adding Cells

--8<-- "README.md:connect-rtu"

!!! warning "You may see messages like `Received un-modeled RTU message msg.channel= ...`. This is expected as we update the Noteable backend services' messaging."

--8<-- "README.md:add-cells"

## Running a Code Cell

--8<-- "README.md:run-code-cell"

## Getting Cell Output

--8<-- "README.md:get-cell-output"