# What is an Environment?

An enviornment is a collection of resources that are used to run a application.

In this project, the resources are:
- Database
- Redis
- My Computer's Hardware

There are primarily two types of environments:
- Pre-Production Environment
- Production Environment

## Pre-Production Environment

There are multiple pre-production environments:
- Local Environment
- E2E Environment (also known as Development Environment)
- QAL Environment (also known as QA Environment)
- PERF Environment (also known as Performance Environment)
- STG Environment (also known as Staging Environment)


### Local Environment

The Local Environment is the environment that is used to run the application on your local machine.

### E2E Environment

The E2E Environment is the environment that is used to run the application on the development server.
It is used to test the application before it is deployed to the production environment.
It is smaller than the production environment and has less data.
This is usually shared with the development team.

### QAL Environment

The QAL Environment is the environment that is used to run the application on the QA server.
It is used to test the application before it is deployed to the production environment.
It is smaller than the production environment and has less data.
This is usually shared with the QA (Quality Assurance) team.

### PERF Environment

The PERF Environment is the environment that is used to run the application on the Performance server.
It is used to test the application before it is deployed to the production environment.
It is used to test the application's performance and scalability.
It has the same resources as the production environment.

### STG Environment

The STG Environment is the environment that is used to run the application on the Staging server.
It is used to test the application before it is deployed to the production environment.
It is smaller than the production environment and has less data.
This is usually shared with the Staging team.

#### Using the STG Environment

The STG environment is the last stop before production, so treat it as a dress rehearsal for a release. Once a build has passed testing in the E2E and QAL environments, deploy it to STG and run final checks and a review of the release by the team. Its configuration (database, Redis) should mirror production as closely as possible, but it must use its own separate resources and non-sensitive or anonymised data, never real customer data. Because it is shared, coordinate with other teams before deploying, and only promote a build to production after it has been verified on STG.


## Production Environment

The Production Environment is the environment that is used to run the application.


The usual flow is:
Local -> E2E -> QAL -> PERF -> STG -> Production

But in some cases,

       |--- E2E
Local -|--- QAL
       |--- PERF

E2E -> STG -> Production
  
