# 빌드: Gradle 래퍼로 실행 가능한 jar 생성
FROM eclipse-temurin:21-jdk AS build
WORKDIR /app
COPY spring/ ./
RUN chmod +x gradlew && ./gradlew bootJar --no-daemon

# 실행: JRE 만 포함 (리버스 프록시가 spring:8080 으로 넘김)
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
