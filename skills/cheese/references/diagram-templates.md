# Diagram templates

Copy one template, then replace the synthetic Shop names with the elements that the change touches.
Pick the template with the checklist and the view table in [`diagrams.md`](diagrams.md).
Each template follows the notation and Mermaid rules in that file.
The C4 views copy the view types of Structurizr. The other templates use UML-style Mermaid diagrams.

| Template | Structurizr or UML equivalent | Mermaid form |
| --- | --- | --- |
| [System Landscape](#system-landscape) | `systemLandscape` view | `flowchart` |
| [System Context](#system-context) | `systemContext` view | `flowchart` |
| [Container](#container) | `container` view | `flowchart` |
| [Component](#component) | `component` view | `flowchart` |
| [Dynamic: sequence form](#dynamic-sequence-form) | `dynamic` view | `sequenceDiagram` |
| [Dynamic: collaboration form](#dynamic-collaboration-form) | `dynamic` view as Structurizr draws it | `flowchart` |
| [Deployment](#deployment) | `deployment` view | `flowchart` |
| [Sequence: request and response](#sequence-request-and-response) | UML sequence diagram | `sequenceDiagram` |
| [Sequence: asynchronous work](#sequence-asynchronous-work) | UML sequence diagram | `sequenceDiagram` |
| [Sequence: agent handoff](#sequence-agent-handoff) | UML sequence diagram | `sequenceDiagram` |
| [Database: entity relationship](#database-entity-relationship) | ER diagram, crow's foot notation | `erDiagram` |
| [Database: UML tables](#database-uml-tables) | UML class diagram with `<<table>>` | `classDiagram` |
| [State](#state) | UML state machine | `stateDiagram-v2` |

Do not copy the Structurizr filtered, custom, or image views. Draw a smaller C4 view instead.

## System Landscape

Use a System Landscape view when a change touches more than one software system that the organization owns.
Show people and software systems only. Do not show containers.

```mermaid
flowchart TB
  Buyer["Buyer<br>[Person]"]
  Agent["Support agent<br>[Person]"]
  subgraph Org["Acme [Enterprise]"]
    Shop["Shop<br>[Software system]<br>Sells goods online"]
    Desk["Support desk<br>[Software system]<br>Tracks tickets"]
    Depot["Warehouse<br>[Software system]<br>Ships orders"]
  end
  Pay["Payment provider<br>[External system]<br>Charges cards"]
  Buyer -->|"buys goods"| Shop
  Agent -->|"handles tickets"| Desk
  Shop -->|"sends orders<br>[Events]"| Depot
  Desk -->|"reads orders<br>[REST]"| Shop
  Shop -->|"charges cards<br>[HTTPS]"| Pay
```

Title: `System Landscape view: Acme`.

## System Context

Use a System Context view when a change adds a user type or an external dependency of one software system.
Show the one system in scope, its people, and its external systems.

```mermaid
flowchart LR
  Buyer["Buyer<br>[Person]"]
  Shop["Shop<br>[Software system]<br>Sells goods online"]
  Pay["Payment provider<br>[External system]<br>Charges cards"]
  Mail["Email service<br>[External system]<br>Sends receipts"]
  Buyer -->|"browses and buys"| Shop
  Shop -->|"charges cards<br>[HTTPS]"| Pay
  Shop -->|"sends receipts<br>[SMTP]"| Mail
```

Title: `System Context view: Shop`.

## Container

Use a Container view when a change adds, removes, or rewires an application, a data store, a queue, or an external system.
Put the containers of the system in scope inside one `subgraph`.

```mermaid
flowchart LR
  Buyer["Buyer<br>[Person]"]
  subgraph Shop["Shop [Software system]"]
    Web["Storefront<br>[Container: React SPA]<br>Shows the cart"]
    API["Orders API<br>[Container: Go service]<br>Places orders"]
    Queue[["Charge queue<br>[Container: SQS]<br>Holds charge jobs"]]
    Worker["Charge worker<br>[Container: Go]<br>Retries card charges"]
    DB[("Orders DB<br>[Container: PostgreSQL]<br>Stores orders")]
  end
  Pay["Payment provider<br>[External system]<br>Charges cards"]
  Buyer -->|"checks out"| Web
  Web -->|"submits order<br>[JSON/HTTPS]"| API
  API -->|"writes order<br>[SQL]"| DB
  API -.->|"enqueues charge<br>[SQS]"| Queue
  Queue -.->|"delivers job"| Worker
  Worker -->|"charges card<br>[HTTPS]"| Pay
  Worker -->|"marks paid<br>[SQL]"| DB
```

Title: `Container view: Shop checkout`.
Legend: cylinder = data store, double-edged box = queue, dashed arrow = asynchronous message.

## Component

Use a Component view when a change restructures the inside of one container.
Put the components of that container inside one `subgraph`. Show the neighbor containers outside it.

```mermaid
flowchart LR
  Web["Storefront<br>[Container: React SPA]"]
  subgraph API["Orders API [Container: Go service]"]
    Handler["Checkout handler<br>[Component: HTTP]<br>Parses requests"]
    Service["Order service<br>[Component]<br>Validates and prices"]
    Repo["Order repository<br>[Component]<br>Reads and writes orders"]
    Pub["Charge publisher<br>[Component]<br>Enqueues charge jobs"]
  end
  DB[("Orders DB<br>[Container: PostgreSQL]")]
  Queue[["Charge queue<br>[Container: SQS]"]]
  Web -->|"POST /orders<br>[JSON/HTTPS]"| Handler
  Handler -->|"places order"| Service
  Service -->|"saves order"| Repo
  Service -->|"requests charge"| Pub
  Repo -->|"SQL"| DB
  Pub -.->|"SQS"| Queue
```

Title: `Component view: Orders API`.

## Dynamic: sequence form

Use a Dynamic view when the order of messages between C4 elements matters, for example a new step in checkout.
Use C4 element names as participants. Number each step with `autonumber`.

```mermaid
sequenceDiagram
  autonumber
  actor Buyer
  participant Web as Storefront
  participant API as Orders API
  participant DB as Orders DB
  participant Queue as Charge queue
  Buyer->>Web: Click Pay
  Web->>API: Submit order [JSON/HTTPS]
  API->>DB: Write order [SQL]
  API-)Queue: Enqueue charge [SQS]
  API-->>Web: 202 Accepted
```

Title: `Dynamic view: Shop checkout`.

## Dynamic: collaboration form

Use the collaboration form when the reader needs the C4 layout and the order together.
Structurizr draws dynamic views this way. Put the step number in front of each relationship label.

```mermaid
flowchart LR
  Buyer["Buyer<br>[Person]"]
  Web["Storefront<br>[Container: React SPA]"]
  API["Orders API<br>[Container: Go service]"]
  DB[("Orders DB<br>[Container: PostgreSQL]")]
  Queue[["Charge queue<br>[Container: SQS]"]]
  Buyer -->|"(1) clicks Pay"| Web
  Web -->|"(2) submits order<br>[JSON/HTTPS]"| API
  API -->|"(3) writes order<br>[SQL]"| DB
  API -.->|"(4) enqueues charge<br>[SQS]"| Queue
```

Title: `Dynamic view: Shop checkout`.

## Deployment

Use a Deployment view when a change moves a container to a new runtime, host, cluster, region, or environment.
Nest one `subgraph` per deployment node. Show each container instance inside the node that runs it.

```mermaid
flowchart TB
  subgraph Cloud["Amazon Web Services [Deployment node]"]
    subgraph Region["us-east-1 [Deployment node: Region]"]
      LB["Load balancer<br>[Infrastructure node: ALB]"]
      subgraph Cluster["EKS cluster [Deployment node: Kubernetes]"]
        API["Orders API<br>[Container instance] x3"]
        Worker["Charge worker<br>[Container instance] x2"]
      end
      subgraph Rds["RDS [Deployment node: PostgreSQL 16]"]
        DB[("Orders DB<br>[Container instance]")]
      end
    end
  end
  LB -->|"HTTPS"| API
  API -->|"SQL over TLS"| DB
  Worker -->|"SQL over TLS"| DB
```

Title: `Deployment view: Shop, production`.

## Sequence: request and response

Use this sequence when a change adds a synchronous call or a new error path.
Show the success path and each error path in one `alt` block.

```mermaid
sequenceDiagram
  autonumber
  participant Web as Storefront
  participant API as Orders API
  participant DB as Orders DB
  Web->>API: POST /orders [JSON/HTTPS]
  activate API
  API->>DB: SELECT stock [SQL]
  DB-->>API: Stock rows
  alt stock available
    API->>DB: INSERT order [SQL]
    API-->>Web: 201 Created
  else stock missing
    API-->>Web: 409 Conflict
  end
  deactivate API
```

## Sequence: asynchronous work

Use this sequence when a change adds a queue, a retry, a callback, or a background job.
Use `-)` for an asynchronous message. Show the retry with `loop` and the failure with `opt`.

```mermaid
sequenceDiagram
  autonumber
  participant API as Orders API
  participant Queue as Charge queue
  participant Worker as Charge worker
  participant Pay as Payment provider
  API-)Queue: Enqueue charge(order_id)
  Queue-)Worker: Deliver job
  loop Up to 3 attempts
    Worker->>Pay: Charge card [HTTPS]
    Pay-->>Worker: Result
  end
  opt All attempts fail
    Worker-)Queue: Move job to dead-letter queue
  end
  Note over Worker,Pay: Idempotency key is order_id
```

## Sequence: agent handoff

Use this sequence when a change alters the order of handoffs between skills, agents, or sub-agents.
Show each artifact that moves between participants.

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant Mold as /mold
  participant Cook as /cook
  participant Coder as coder sub-agent
  participant Press as /press
  User->>Mold: Describe the feature
  Mold-->>User: Spec for approval
  User->>Cook: Approve the spec
  Cook->>Coder: Dispatch brief with acceptance criteria
  Coder-->>Cook: Diff and gate results
  Cook->>Press: Hand off the changed files
  Press-->>Cook: Hardened tests
```

## Database: entity relationship

Use an entity relationship diagram when a change adds or alters tables, columns, keys, or relationships.
Show only the tables that the change touches, plus the tables that they reference.
Mark keys with `PK`, `FK`, and `UK`.

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ LINE_ITEM : contains
  ORDER ||--o| PAYMENT : "paid by"
  CUSTOMER {
    uuid id PK
    string email UK
  }
  ORDER {
    uuid id PK
    uuid customer_id FK
    string status
    timestamp created_at
  }
  LINE_ITEM {
    uuid order_id PK, FK
    string sku PK
    int qty
    numeric unit_price
  }
  PAYMENT {
    uuid id PK
    uuid order_id FK, UK
    string provider_ref
  }
```

Cardinality: `||` exactly one, `o|` zero or one, `|{` one or more, `o{` zero or more.

## Database: UML tables

Use the UML table form when the reader needs column types, constraints, or indexes that the entity relationship form cannot show.
Mark each class with the `<<table>>` stereotype. Put multiplicities on each association.

```mermaid
classDiagram
  class customers {
    <<table>>
    uuid id PK
    text email UNIQUE
  }
  class orders {
    <<table>>
    uuid id PK
    uuid customer_id FK
    text status CHECK in pending, paid, failed
    timestamptz created_at INDEX
  }
  class payments {
    <<table>>
    uuid id PK
    uuid order_id FK UNIQUE
    text provider_ref
  }
  customers "1" --> "0..*" orders : places
  orders "1" --> "0..1" payments : paid by
```

## State

Use a state diagram when a change adds a status field, a lifecycle, or a new transition.
Label each transition with the event that causes it.

```mermaid
stateDiagram-v2
  [*] --> Pending
  Pending --> Paid: charge succeeded
  Pending --> Failed: retries exhausted
  Paid --> Shipped: label printed
  Failed --> [*]
  Shipped --> [*]
```
